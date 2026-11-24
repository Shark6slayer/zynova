from fastapi import APIRouter, HTTPException, status, Depends
from datetime import datetime, timezone, timedelta
import asyncio
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from app.schemas.all_schemas import (
    UserRegister, UserLogin, TokenResponse, 
    TokenRefreshRequest, UserProfileResponse,
    VerifyEmailRequest, ResendVerificationRequest,
    ForgotPasswordRequest, VerifyResetCodeRequest,
    ResetPasswordRequest, AuthStatusResponse
)
from app.core.security import (
    get_password_hash, verify_password, 
    create_access_token, create_refresh_token, decode_token
)
from app.core.otp_service import OTPService
from app.services.verification_service import (
    VerificationService,
    PURPOSE_REGISTRATION,
    OTP_EXPIRY_MINUTES,
    generate_verification_id,
    generate_six_digit_otp,
    compute_registration_otp_hash,
    verify_registration_otp_hash
)
from app.services.email_service import EmailService
from app.database.client import get_database
from app.api.deps import get_current_user, get_current_user_payload
from app.core.token_revocation import revoke_token

import time
import logging
import re
from app.core.rate_limit import (
    check_auth_rate_limit,
    check_email_verify_rate_limit,
    check_email_resend_rate_limit,
    auth_rate_limiter,
    email_verify_rate_limiter,
    email_resend_rate_limiter
)
from app.core.audit_ledger import record_audit_event

logger = logging.getLogger("super_ai.auth")

router = APIRouter(prefix="/auth", tags=["Authentication"])

def validate_password_complexity(password: str) -> None:
    if len(password) < 8:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must be at least 8 characters long."
        )
    if not re.search(r"\d", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one digit."
        )
    if not re.search(r"[a-zA-Z]", password):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Password must contain at least one letter."
        )

# --------------------------------------------------------------------------
# 1. Registration & Email Verification
# --------------------------------------------------------------------------

@router.post("/register", response_model=AuthStatusResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(check_auth_rate_limit)])
async def register(user_in: UserRegister):
    validate_password_complexity(user_in.password)

    clean_email = user_in.email.lower().strip()
    clean_username = user_in.username.lower().strip()

    # Rate limit by normalized email in addition to IP
    await auth_rate_limiter.check_async(f"register_email:{clean_email}")

    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    # 1 & 2. Concurrently check for existing user and pending registration
    user_query = {"$or": [{"email": clean_email}, {"username": clean_username}]}
    existing_user, pending_reg = await asyncio.gather(
        db.users.find_one(user_query),
        db.pending_registrations.find_one(user_query)
    )
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email or username already exists."
        )

    now = datetime.now(timezone.utc)
    if pending_reg:
        # If username matches another pending email, block collision
        if pending_reg.get("username") == clean_username and pending_reg.get("email") != clean_email:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="An account with this username already exists."
            )
        # If pending registration has expired, remove it
        exp = pending_reg.get("expires_at")
        if exp:
            if exp.tzinfo is None:
                exp = exp.replace(tzinfo=timezone.utc)
            if exp < now:
                await db.pending_registrations.delete_one({"_id": pending_reg["_id"]})

    # 3. Generate verification challenge
    # 6-digit OTP using secrets.randbelow(1_000_000), zero-padded
    # otp_hash = HMAC-SHA256(server secret from env, f"{email}:{otp}:{verification_id}")
    v_id = generate_verification_id()
    otp_code = generate_six_digit_otp()
    otp_hash = compute_registration_otp_hash(clean_email, otp_code, v_id)

    # 4. Save/update temporary record in 'pending_registrations' collection (NEVER in 'users')
    # Store ONLY the hash in pending_registrations (with attempts=0, expires_at, hashed password).
    hashed_pwd = await asyncio.to_thread(get_password_hash, user_in.password)
    expires_at = now + timedelta(minutes=OTP_EXPIRY_MINUTES)
    pending_doc = {
        "email": clean_email,
        "username": clean_username,
        "full_name": user_in.full_name.strip(),
        "hashed_password": hashed_pwd,
        "verification_id": v_id,
        "otp_hash": otp_hash,
        "attempts": 0,
        "resend_count": 0,
        "resend_eligible_at": now + timedelta(seconds=60),
        "created_at": now,
        "expires_at": expires_at
    }

    try:
        await db.pending_registrations.update_one(
            {"email": clean_email},
            {"$set": pending_doc},
            upsert=True
        )
    except DuplicateKeyError:
        # Prevent 500 when concurrent request attempts registration or key collision occurs
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email or username already exists."
        )

    # Also mirror into legacy/in-memory OTPService for backward compatibility
    await OTPService.create_email_verification_otp(clean_email)

    # 5. Deliver OTP via Zoho Catalyst Email Service
    email_sent = False
    try:
        email_sent = await EmailService.send_verification_otp(
            to_email=clean_email,
            otp_code=otp_code,
            expiration_minutes=OTP_EXPIRY_MINUTES
        )
    except Exception as e:
        logger.error(f"Failed to dispatch verification email to {clean_email}: {e}")
        email_sent = False

    if not email_sent:
        # Atomic rollback: delete pending record, return generic 500
        logger.warning(f"Registration email delivery failed for {clean_email}. Rolling back pending registration.")
        await db.pending_registrations.delete_one({"email": clean_email})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to send verification email. Please try again later."
        )

    await record_audit_event(
        event_type="AUTH_REGISTER_PENDING_VERIFICATION",
        raw_actor_id=clean_email,
        metadata={"action": "register_pending_verification", "verification_id": v_id}
    )

    return AuthStatusResponse(
        status="verification_required",
        message="A 6-digit verification code has been sent to your email address.",
        email=clean_email,
        id=None,
        username=clean_username,
        full_name=pending_doc["full_name"],
        verification_id=v_id,
        cooldown_seconds=60,
        expires_in_seconds=OTP_EXPIRY_MINUTES * 60
    )


@router.post("/verify-email", response_model=AuthStatusResponse, dependencies=[Depends(check_email_verify_rate_limit)])
async def verify_email(data: VerifyEmailRequest):
    clean_email = data.email.lower().strip()
    # Rate limit by normalized email in addition to IP
    await email_verify_rate_limiter.check_async(f"email:{clean_email}")

    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    # 1. Check if already verified in permanent users collection
    existing_user = await db.users.find_one({"email": clean_email})
    if existing_user and existing_user.get("is_verified") is True:
        return AuthStatusResponse(
            status="verified",
            message="Email is already verified. You can log in.",
            email=clean_email,
            id=str(existing_user["_id"])
        )

    # 2. Check pending registration or legacy unverified user
    pending_reg = await db.pending_registrations.find_one({"email": clean_email})
    if not pending_reg and not existing_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")

    now = datetime.now(timezone.utc)

    # 3. Verify OTP against pending_registration
    if pending_reg:
        # Check attempts limit and expiration
        current_attempts = pending_reg.get("attempts", 0)
        expires_at = pending_reg.get("expires_at")
        if expires_at and expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)

        if (expires_at and now > expires_at) or current_attempts >= 5:
            # Delete pending record and require re-registration
            await db.pending_registrations.delete_one({"_id": pending_reg["_id"]})
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")

        # Compare HMAC
        v_id = pending_reg.get("verification_id", "")
        stored_hash = pending_reg.get("otp_hash", "")
        is_match = False
        if stored_hash:
            is_match = verify_registration_otp_hash(clean_email, data.code, v_id, stored_hash)

        # Fallback check against legacy VerificationService/OTPService if hash was from old format
        if not is_match and not stored_hash:
            legacy_ok, _, _ = await VerificationService.verify_otp(
                email=clean_email,
                submitted_otp=data.code,
                purpose=PURPOSE_REGISTRATION,
                verification_id=data.verification_id or v_id
            )
            is_match = legacy_ok

        if not is_match:
            # Atomic increment of attempts using find_one_and_update
            updated_doc = await db.pending_registrations.find_one_and_update(
                {"_id": pending_reg["_id"]},
                {
                    "$inc": {"attempts": 1},
                    "$set": {"updated_at": now}
                },
                return_document=ReturnDocument.AFTER
            )
            if updated_doc and updated_doc.get("attempts", 0) >= 5:
                # Delete pending record upon reaching 5 or more failed attempts
                await db.pending_registrations.delete_one({"_id": pending_reg["_id"]})

            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")

        # Match: atomically find_one_and_delete from pending_registrations, create user in users
        deleted_pending = await db.pending_registrations.find_one_and_delete({"_id": pending_reg["_id"]})
        if not deleted_pending:
            # Reused OTP or concurrent consumption
            already_user = await db.users.find_one({"email": clean_email})
            if already_user:
                return AuthStatusResponse(
                    status="verified",
                    message="Email verified successfully. You can now log in.",
                    email=clean_email,
                    id=str(already_user["_id"])
                )
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")

        verified_at = now
        new_user_doc = {
            "email": clean_email,
            "username": deleted_pending["username"],
            "full_name": deleted_pending["full_name"],
            "hashed_password": deleted_pending["hashed_password"],
            "is_active": True,
            "is_verified": True,
            "verified_at": verified_at,
            "created_at": deleted_pending.get("created_at", verified_at),
            "updated_at": verified_at
        }
        res = await db.users.insert_one(new_user_doc)
        user_id = str(res.inserted_id)

        # Initialize default user preferences
        await db.user_preferences.insert_one({
            "user_id": user_id,
            "theme": "midnight-glass",
            "language": "en",
            "accentColor": "#8b5cf6",
            "reducedMotion": False,
            "fontSize": "normal",
            "compactSidebar": False,
            "currency": "INR",
            "aiMemoryEnabled": True,
            "pinnedModules": ["home", "ai-assistant", "search", "chat", "food", "payments"],
            "hiddenModules": [],
            "onboardingCompleted": True,
            "updated_at": verified_at
        })

        await record_audit_event(
            event_type="AUTH_EMAIL_VERIFIED",
            raw_actor_id=user_id,
            metadata={"action": "email_verified", "verification_id": v_id}
        )

        return AuthStatusResponse(
            status="verified",
            message="Email verified successfully. You can now log in.",
            email=clean_email,
            id=user_id,
            verification_id=v_id
        )

    elif existing_user:
        # Legacy unverified account transition
        user_id = str(existing_user["_id"])
        verified_at = now
        await db.users.update_one(
            {"_id": existing_user["_id"]},
            {"$set": {"is_verified": True, "verified_at": verified_at, "updated_at": verified_at}}
        )
        return AuthStatusResponse(
            status="verified",
            message="Email verified successfully. You can now log in.",
            email=clean_email,
            id=user_id
        )


@router.post("/resend-otp", response_model=AuthStatusResponse, dependencies=[Depends(check_email_resend_rate_limit)])
@router.post("/resend-verification-code", response_model=AuthStatusResponse, dependencies=[Depends(check_email_resend_rate_limit)])
async def resend_verification_code(data: ResendVerificationRequest):
    clean_email = data.email.lower().strip()
    # Rate limit by normalized email (max 3 per hour / 60s cooldown) in addition to IP
    await email_resend_rate_limiter.check_async(f"resend_email:{clean_email}")

    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    now = datetime.now(timezone.utc)

    # Generic response message for anti-enumeration
    generic_response = AuthStatusResponse(
        status="sent",
        message="If an unverified account exists with this email, a new verification code has been sent.",
        email=clean_email
    )

    # 1. If already verified, return generic response (no user enumeration)
    existing_user = await db.users.find_one({"email": clean_email})
    if existing_user and existing_user.get("is_verified") is True:
        return generic_response

    # 2. Check pending registration
    pending_reg = await db.pending_registrations.find_one({"email": clean_email})
    if not pending_reg and not existing_user:
        return generic_response

    # Cooldown check: 60 seconds per email
    if pending_reg:
        resend_eligible_at = pending_reg.get("resend_eligible_at")
        if resend_eligible_at:
            if resend_eligible_at.tzinfo is None:
                resend_eligible_at = resend_eligible_at.replace(tzinfo=timezone.utc)
            if now < resend_eligible_at:
                cd_rem = int((resend_eligible_at - now).total_seconds()) + 1
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Please wait {cd_rem} seconds before requesting a new code."
                )

    # Generate fresh OTP and hash
    v_id = generate_verification_id()
    new_code = generate_six_digit_otp()
    new_hash = compute_registration_otp_hash(clean_email, new_code, v_id)
    new_expires = now + timedelta(minutes=OTP_EXPIRY_MINUTES)
    new_eligible = now + timedelta(seconds=60)

    if pending_reg:
        # Replace the old one, reset expiry, reset attempts
        await db.pending_registrations.update_one(
            {"_id": pending_reg["_id"]},
            {
                "$set": {
                    "verification_id": v_id,
                    "otp_hash": new_hash,
                    "attempts": 0,
                    "expires_at": new_expires,
                    "resend_eligible_at": new_eligible,
                    "updated_at": now
                },
                "$inc": {"resend_count": 1}
            }
        )

    # Mirror into OTPService for backward compatibility
    await OTPService.create_email_verification_otp(clean_email)

    try:
        sent = await EmailService.send_verification_otp(to_email=clean_email, otp_code=new_code, expiration_minutes=OTP_EXPIRY_MINUTES)
        if not sent:
            logger.error(f"Email service reported delivery failure for resend to {clean_email}")
    except Exception as e:
        logger.error(f"Failed to resend verification email to {clean_email}: {e}")

    return generic_response


# --------------------------------------------------------------------------
# 2. Login & Token Management
# --------------------------------------------------------------------------

@router.post("/login", response_model=TokenResponse, dependencies=[Depends(check_auth_rate_limit)])
async def login(credentials: UserLogin):
    t_start = time.perf_counter()
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    clean_email = credentials.email.lower().strip()
    t_db_pre = time.perf_counter()
    user = await db.users.find_one({"email": clean_email})
    t_db_post = time.perf_counter()

    is_valid = False
    if user and user.get("hashed_password"):
        is_valid = await asyncio.to_thread(verify_password, credentials.password, user["hashed_password"])

    if not user or not is_valid:
        t_pwd = time.perf_counter()
        logger.info(
            f"[LoginTiming] Lookup: {round((t_db_post - t_db_pre) * 1000, 1)}ms | "
            f"Verify: {round((t_pwd - t_db_post) * 1000, 1)}ms | Outcome: FAILURE"
        )
        await record_audit_event(
            event_type="AUTH_FAILURE",
            raw_actor_id=None,
            metadata={"reason": "bad_credentials"}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    # Mandatory Email Verification Enforcement
    # Note: legacy accounts where is_verified is missing/None are grandfathered as verified
    if user.get("is_verified") is False:
        logger.warning(f"Login blocked for unverified account: {clean_email}")
        await record_audit_event(
            event_type="AUTH_BLOCKED_UNVERIFIED",
            raw_actor_id=str(user["_id"]),
            metadata={"action": "blocked_unverified"}
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Please verify your email before logging in.",
            headers={"X-Error-Code": "EMAIL_NOT_VERIFIED"}
        )

    # Block login if account is pending deletion
    if user.get("account_status") == "pending_deletion":
        deletion_requested_at = user.get("deletion_requested_at")
        permanent_deletion_at = user.get("permanent_deletion_at")
        logger.warning(f"Login blocked for account pending deletion: {clean_email}")
        await record_audit_event(
            event_type="AUTH_BLOCKED_PENDING_DELETION",
            raw_actor_id=str(user["_id"]),
            metadata={"action": "blocked_pending_deletion"}
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="This account is currently scheduled for deletion. You can restore access via the account recovery endpoint.",
            headers={
                "X-Error-Code": "ACCOUNT_PENDING_DELETION",
                "X-Permanent-Deletion-At": permanent_deletion_at.isoformat() if permanent_deletion_at else ""
            }
        )

    t_pwd = time.perf_counter()
    user_id = str(user["_id"])
    access_token = create_access_token({"sub": user_id, "email": user["email"]})
    refresh_token = create_refresh_token({"sub": user_id, "email": user["email"]})
    t_token = time.perf_counter()

    # Concurrently persist refresh token and record audit event
    await asyncio.gather(
        db.refresh_tokens.update_one(
            {"user_id": user_id},
            {"$set": {"token": refresh_token, "updated_at": datetime.now(timezone.utc)}},
            upsert=True
        ),
        record_audit_event(
            event_type="AUTH_SUCCESS",
            raw_actor_id=user_id,
            metadata={"method": "password"}
        )
    )
    t_writes = time.perf_counter()

    user_profile = UserProfileResponse(
        id=user_id,
        email=user["email"],
        username=user["username"],
        full_name=user["full_name"],
        avatar_url=user.get("avatar_url"),
        bio=user.get("bio"),
        created_at=user.get("created_at", datetime.now(timezone.utc)),
        is_active=user.get("is_active", True),
        is_verified=user.get("is_verified", True),
        verified_at=user.get("verified_at")
    )

    t_total = time.perf_counter()
    logger.info(
        f"[LoginTiming] Lookup: {round((t_db_post - t_db_pre) * 1000, 1)}ms | "
        f"Argon2: {round((t_pwd - t_db_post) * 1000, 1)}ms | "
        f"Token: {round((t_token - t_pwd) * 1000, 1)}ms | "
        f"Writes: {round((t_writes - t_token) * 1000, 1)}ms | "
        f"Total: {round((t_total - t_start) * 1000, 1)}ms"
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        refresh_token=refresh_token,
        user=user_profile
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token_endpoint(data: TokenRefreshRequest):
    payload = decode_token(data.refresh_token)
    if not payload or payload.get("type") != "refresh":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    user_id = payload.get("sub")
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    stored_token = await db.refresh_tokens.find_one({"user_id": user_id, "token": data.refresh_token})
    if not stored_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Revoked or expired refresh token")

    # Enforce email verification on refresh token
    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user or user.get("is_verified") is False:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Email not verified. Refresh token rejected.",
            headers={"X-Error-Code": "EMAIL_NOT_VERIFIED"}
        )

    new_access_token = create_access_token({"sub": user_id, "email": payload.get("email")})
    new_refresh_token = create_refresh_token({"sub": user_id, "email": payload.get("email")})

    await db.refresh_tokens.update_one(
        {"user_id": user_id},
        {"$set": {"token": new_refresh_token, "updated_at": datetime.now(timezone.utc)}}
    )

    return TokenResponse(
        access_token=new_access_token,
        token_type="bearer",
        refresh_token=new_refresh_token
    )


@router.post("/logout", status_code=status.HTTP_200_OK)
async def logout(
    current_user: dict = Depends(get_current_user),
    payload: dict = Depends(get_current_user_payload)
):
    db = get_database()
    if db is not None:
        await db.refresh_tokens.delete_many({"user_id": current_user["id"]})

    jti = payload.get("jti")
    exp = payload.get("exp")
    if jti and exp:
        exp_dt = datetime.fromtimestamp(exp, tz=timezone.utc)
        await revoke_token(jti=jti, expires_at=exp_dt, reason="logout", user_id=current_user["id"])

    await record_audit_event(
        event_type="AUTH_LOGOUT",
        raw_actor_id=current_user["id"],
        metadata={"session_revoked": bool(jti)}
    )

    return {"status": "logged_out", "detail": "Session revoked"}


@router.get("/me", response_model=UserProfileResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    return UserProfileResponse(
        id=current_user["id"],
        email=current_user["email"],
        username=current_user["username"],
        full_name=current_user["full_name"],
        avatar_url=current_user.get("avatar_url"),
        bio=current_user.get("bio"),
        created_at=current_user.get("created_at", datetime.now(timezone.utc)),
        is_active=current_user.get("is_active", True),
        is_verified=current_user.get("is_verified", True),
        verified_at=current_user.get("verified_at")
    )


# --------------------------------------------------------------------------
# 3. Forgot Password & Reset Password Workflow
# --------------------------------------------------------------------------

@router.post("/forgot-password", response_model=AuthStatusResponse, dependencies=[Depends(check_auth_rate_limit)])
async def forgot_password(data: ForgotPasswordRequest):
    clean_email = data.email.lower().strip()
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    user = await db.users.find_one({"email": clean_email})
    if user:
        code, ok, cd_remaining = await OTPService.create_password_reset_code(clean_email)
        if ok:
            try:
                await EmailService.send_password_reset_otp(to_email=clean_email, reset_code=code, expiration_minutes=10)
                await record_audit_event(
                    event_type="AUTH_PASSWORD_RESET_REQUESTED",
                    raw_actor_id=str(user["_id"]),
                    metadata={"action": "reset_requested"}
                )
            except Exception as e:
                logger.error(f"Failed to dispatch password reset email to {clean_email}: {e}")
        else:
            logger.info(f"Password reset request in cooldown for {clean_email} ({cd_remaining}s remaining)")

    # Anti-enumeration: always return generic response
    return AuthStatusResponse(
        status="success",
        message="If an account exists with this email address, a 6-digit password reset code has been sent.",
        email=clean_email
    )


@router.post("/verify-reset-code", response_model=AuthStatusResponse, dependencies=[Depends(check_auth_rate_limit)])
async def verify_reset_code(data: VerifyResetCodeRequest):
    clean_email = data.email.lower().strip()
    ok, msg, reset_token = await OTPService.verify_password_reset_code(clean_email, data.code)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)

    return AuthStatusResponse(
        status="valid",
        message=msg,
        email=clean_email,
        reset_token=reset_token
    )


@router.post("/reset-password", response_model=AuthStatusResponse, dependencies=[Depends(check_auth_rate_limit)])
async def reset_password(data: ResetPasswordRequest):
    clean_email = data.email.lower().strip()
    validate_password_complexity(data.new_password)

    if data.confirm_password is not None and data.new_password != data.confirm_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Passwords do not match.")

    # Validate and consume single-use reset token
    ok, err_msg = await OTPService.consume_password_reset_token(clean_email, data.reset_token)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=err_msg)

    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    user = await db.users.find_one({"email": clean_email})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found.")

    new_hash = await asyncio.to_thread(get_password_hash, data.new_password)
    now = datetime.now(timezone.utc)

    # Concurrently update password and invalidate all active refresh tokens/sessions
    user_id = str(user["_id"])
    await asyncio.gather(
        db.users.update_one(
            {"_id": user["_id"]},
            {"$set": {"hashed_password": new_hash, "updated_at": now}}
        ),
        db.refresh_tokens.delete_many({"user_id": user_id}),
        record_audit_event(
            event_type="AUTH_PASSWORD_RESET_SUCCESS",
            raw_actor_id=user_id,
            metadata={"action": "reset_success"}
        )
    )

    return AuthStatusResponse(
        status="success",
        message="Password has been successfully reset. Please log in with your new password.",
        email=clean_email
    )
