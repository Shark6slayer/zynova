from fastapi import APIRouter, HTTPException, status, Depends
from datetime import datetime, timezone
from bson import ObjectId
from app.schemas.all_schemas import (
    UserRegister, UserLogin, TokenResponse, 
    TokenRefreshRequest, UserProfileResponse
)
from app.core.security import (
    get_password_hash, verify_password, 
    create_access_token, create_refresh_token, decode_token
)
from app.database.client import get_database
from app.api.deps import get_current_user, get_current_user_payload
from app.core.token_revocation import revoke_token

import re
from app.core.rate_limit import check_auth_rate_limit
from app.core.audit_ledger import record_audit_event

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

@router.post("/register", response_model=UserProfileResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(check_auth_rate_limit)])
async def register(user_in: UserRegister):
    validate_password_complexity(user_in.password)

    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    # Check for existing email or username
    existing_user = await db.users.find_one({
        "$or": [{"email": user_in.email.lower().strip()}, {"username": user_in.username.lower().strip()}]
    })
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email or username already exists."
        )


    user_doc = {
        "email": user_in.email.lower(),
        "username": user_in.username.lower(),
        "full_name": user_in.full_name,
        "hashed_password": get_password_hash(user_in.password),
        "is_active": True,
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

    return UserProfileResponse(
        id=user_id,
        email=user_doc["email"],
        username=user_doc["username"],
        full_name=user_doc["full_name"],
        created_at=user_doc["created_at"],
        is_active=True
    )

@router.post("/login", response_model=TokenResponse, dependencies=[Depends(check_auth_rate_limit)])
async def login(credentials: UserLogin):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    user = await db.users.find_one({"email": credentials.email.lower().strip()})
    if not user or not verify_password(credentials.password, user["hashed_password"]):
        await record_audit_event(
            event_type="AUTH_FAILURE",
            raw_actor_id=None,
            metadata={"reason": "bad_credentials"}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password"
        )

    user_id = str(user["_id"])
    access_token = create_access_token({"sub": user_id, "email": user["email"]})
    refresh_token = create_refresh_token({"sub": user_id, "email": user["email"]})

    # Store refresh token for revocation tracking
    await db.refresh_tokens.update_one(
        {"user_id": user_id},
        {"$set": {"token": refresh_token, "updated_at": datetime.now(timezone.utc)}},
        upsert=True
    )

    await record_audit_event(
        event_type="AUTH_SUCCESS",
        raw_actor_id=user_id,
        metadata={"method": "password"}
    )

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        refresh_token=refresh_token
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

    new_access_token = create_access_token({"sub": user_id, "email": payload.get("email")})
    new_refresh_token = create_refresh_token({"sub": user_id, "email": payload.get("email")})


    if db is not None:
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
        is_active=current_user.get("is_active", True)
    )
