from fastapi import APIRouter, HTTPException, status, Depends
from datetime import datetime, timezone
import asyncio
from bson import ObjectId
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
from app.services.email_service import EmailService
from app.database.client import get_database
from app.api.deps import get_current_user, get_current_user_payload
from app.core.token_revocation import revoke_token

import time
import logging
import re
from app.core.rate_limit import check_auth_rate_limit
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

    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    clean_email = user_in.email.lower().strip()
    clean_username = user_in.username.lower().strip()

    # Check for existing email or username
    existing_user = await db.users.find_one({
        "$or": [{"email": clean_email}, {"username": clean_username}]
    })
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email or username already exists."
        )

    # Create unverified user account
    user_doc = {
        "email": clean_email,
        "username": clean_username,
        "full_name": user_in.full_name.strip(),
        "hashed_password": get_password_hash(user_in.password),
        "is_active": True,
        "is_verified": False,
        "verified_at": None,
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }

    result = await db.users.insert_one(user_doc)
    user_id = str(result.inserted_id)

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
        "updated_at": datetime.now(timezone.utc)
    })

    # Generate cryptographically secure 6-digit OTP & store in Redis (5-min TTL)
    otp_code, ok, cd_remaining = await OTPService.create_email_verification_otp(clean_email)
    if ok:
        try:
            # Deliver OTP via Titan SMTP
            await EmailService.send_verification_otp(to_email=clean_email, otp_code=otp_code, expiration_minutes=5)
        except Exception as e:
            logger.error(f"Failed to dispatch verification email to {clean_email}: {e}")
            # Note: We do not fail registration, user can resend code

    await record_audit_event(
        event_type="AUTH_REGISTER_PENDING_VERIFICATION",
        raw_actor_id=user_id,
        metadata={"action": "register_pending_verification"}
    )

    return AuthStatusResponse(
        status="verification_required",
        message="Account created. A 6-digit verification code has been sent to your email address.",
        email=clean_email,
        id=user_id,
        username=clean_username,
        full_name=user_doc["full_name"]
    )


@router.post("/verify-email", response_model=AuthStatusResponse, dependencies=[Depends(check_auth_rate_limit)])
async def verify_email(data: VerifyEmailRequest):
    clean_email = data.email.lower().strip()
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    user = await db.users.find_one({"email": clean_email})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found.")

    if user.get("is_verified") is True:
        return AuthStatusResponse(
            status="verified",
            message="Email is already verified. You can log in.",
            email=clean_email
        )

    # Verify 6-digit OTP
    ok, error_msg = await OTPService.verify_email_otp(clean_email, data.code)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=error_msg)

    # Mark user as verified in MongoDB
    verified_at = datetime.now(timezone.utc)
    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {"is_verified": True, "verified_at": verified_at, "updated_at": verified_at}}
    )

    await record_audit_event(
        event_type="AUTH_EMAIL_VERIFIED",
        raw_actor_id=str(user["_id"]),
        metadata={"action": "email_verified"}
    )

    return AuthStatusResponse(
        status="verified",
        message="Email verified successfully. You can now log in.",
        email=clean_email,
        id=str(user["_id"])
    )


@router.post("/resend-verification-code", response_model=AuthStatusResponse, dependencies=[Depends(check_auth_rate_limit)])
async def resend_verification_code(data: ResendVerificationRequest):
    clean_email = data.email.lower().strip()
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    user = await db.users.find_one({"email": clean_email})
    if not user:
        # Anti-enumeration: return standard response
        return AuthStatusResponse(
            status="sent",
            message="If an unverified account exists with this email, a new verification code has been sent.",
            email=clean_email
        )

    if user.get("is_verified") is True:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is already verified.")

    code, ok, cd_remaining = await OTPService.create_email_verification_otp(clean_email)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"Please wait {cd_remaining} seconds before requesting a new code."
        )

    try:
        await EmailService.send_verification_otp(to_email=clean_email, otp_code=code, expiration_minutes=5)
    except Exception as e:
        logger.error(f"Failed to resend verification email to {clean_email}: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to send verification email.")

    return AuthStatusResponse(
        status="sent",
        message="A new verification code has been sent to your email address.",
        email=clean_email
    )


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

    if not user or not verify_password(credentials.password, user["hashed_password"]):
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

    new_hash = get_password_hash(data.new_password)
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
