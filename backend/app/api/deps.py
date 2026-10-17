from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, Dict, Any
from datetime import datetime, timezone
from app.core.security import decode_token
from app.core.token_revocation import is_token_revoked
from app.database.client import get_database
from bson import ObjectId

security_bearer = HTTPBearer(auto_error=False)

async def get_current_user_payload(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)
) -> Dict[str, Any]:
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials not provided",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token = credentials.credentials
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # SEC-06 Revocation check by JTI
    jti = payload.get("jti")
    if jti and await is_token_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has been revoked",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload

async def get_current_user(
    payload: Dict[str, Any] = Depends(get_current_user_payload)
) -> Dict[str, Any]:
    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token subject")
    
    db = get_database()
    if db is None:
        # Fallback simulated test mode
        return {"id": user_id, "email": "dev@superai.in", "username": "ananya_ai", "full_name": "Ananya Sharma"}

    user = await db.users.find_one({"_id": ObjectId(user_id)})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    
    if not user.get("is_active", True):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Account is deactivated")

    # Check user-wide session revocation (password reset, account suspension)
    revoked_before = user.get("tokens_revoked_before")
    if revoked_before:
        iat = payload.get("iat")
        if iat:
            token_iat = datetime.fromtimestamp(iat, tz=timezone.utc) if isinstance(iat, (int, float)) else iat
            if revoked_before.tzinfo is None:
                revoked_before = revoked_before.replace(tzinfo=timezone.utc)
            if token_iat < revoked_before:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Session has been revoked",
                    headers={"WWW-Authenticate": "Bearer"},
                )

    user["id"] = str(user["_id"])
    return user

async def get_optional_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(security_bearer)
) -> Optional[Dict[str, Any]]:
    if not credentials:
        return None
    token = credentials.credentials
    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        return None
    user_id = payload.get("sub")
    if not user_id:
        return None

    # Check JTI revocation
    jti = payload.get("jti")
    if jti and await is_token_revoked(jti):
        return None

    db = get_database()
    if db is None:
        return None
    try:
        user = await db.users.find_one({"_id": ObjectId(user_id)})
        if user and user.get("is_active", True):
            revoked_before = user.get("tokens_revoked_before")
            if revoked_before:
                iat = payload.get("iat")
                if iat:
                    token_iat = datetime.fromtimestamp(iat, tz=timezone.utc) if isinstance(iat, (int, float)) else iat
                    if revoked_before.tzinfo is None:
                        revoked_before = revoked_before.replace(tzinfo=timezone.utc)
                    if token_iat < revoked_before:
                        return None
            user["id"] = str(user["_id"])
            return user
    except Exception:
        pass
    return None
