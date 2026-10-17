import time
import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from app.core.config import settings
from app.core.rate_limit import get_redis_client
from app.database.client import get_database
from app.core.security_logger import log_security_event

logger = logging.getLogger("super_ai.token_revocation")

# In-memory local cache of recently revoked JTIs (jti -> expire_timestamp)
_local_revoked_jtis: Dict[str, float] = {}

def _clean_local_cache():
    now = time.time()
    expired = [k for k, exp in _local_revoked_jtis.items() if exp < now]
    for k in expired:
        _local_revoked_jtis.pop(k, None)

async def revoke_token(
    jti: str,
    expires_at: datetime,
    reason: str = "logout",
    user_id: Optional[str] = None
):
    """
    Revokes an individual access token by jti until its expiry.
    Persists to Redis (if configured) and MongoDB (with TTL index).
    """
    now = datetime.now(timezone.utc)
    # Ensure timezone awareness
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    
    ttl_seconds = max(1, int((expires_at - now).total_seconds()))
    exp_ts = time.time() + ttl_seconds
    _local_revoked_jtis[jti] = exp_ts
    _clean_local_cache()

    # 1. Store in Redis if available
    r_client = await get_redis_client()
    if r_client is not None:
        try:
            await r_client.setex(f"revoked_jti:{jti}", ttl_seconds, "1")
        except Exception as e:
            logger.warning(f"Failed to record revoked JTI in Redis: {e}")

    # 2. Store in MongoDB collection
    db = get_database()
    if db is not None:
        try:
            await db.revoked_tokens.update_one(
                {"jti": jti},
                {"$set": {
                    "jti": jti,
                    "user_id": user_id,
                    "expires_at": expires_at,
                    "reason": reason,
                    "revoked_at": now
                }},
                upsert=True
            )
        except Exception as e:
            logger.warning(f"Failed to record revoked JTI in MongoDB: {e}")

    log_security_event(
        event_code="TOKEN_REVOKED",
        action="revoke_token",
        status="SUCCESS",
        actor_id=user_id,
        details={"jti_prefix": jti[:8], "reason": reason, "ttl": ttl_seconds}
    )

async def is_token_revoked(jti: Optional[str]) -> bool:
    """
    Checks if a token JTI has been revoked.
    Checks memory cache -> Redis -> MongoDB.
    """
    if not jti:
        return False

    # Check local memory cache
    now = time.time()
    if jti in _local_revoked_jtis:
        if _local_revoked_jtis[jti] > now:
            return True
        else:
            _local_revoked_jtis.pop(jti, None)

    # Check Redis
    r_client = await get_redis_client()
    if r_client is not None:
        try:
            val = await r_client.get(f"revoked_jti:{jti}")
            if val is not None:
                return True
        except Exception as e:
            logger.warning(f"Redis JTI check failed: {e}")

    # Check MongoDB
    db = get_database()
    if db is not None:
        try:
            entry = await db.revoked_tokens.find_one({"jti": jti})
            if entry is not None:
                # Add to local cache for subsequent fast-path
                exp = entry.get("expires_at")
                if exp:
                    if exp.tzinfo is None:
                        exp = exp.replace(tzinfo=timezone.utc)
                    _local_revoked_jtis[jti] = exp.timestamp()
                return True
        except Exception as e:
            logger.warning(f"MongoDB JTI check failed: {e}")

    return False

async def revoke_all_user_sessions(user_id: str, reason: str = "security_event"):
    """
    Revokes all active sessions for a user (e.g. password change, account suspension, deletion).
    Deletes refresh tokens and sets tokens_revoked_before timestamp on user document.
    """
    now = datetime.now(timezone.utc)
    db = get_database()
    if db is not None:
        try:
            await db.refresh_tokens.delete_many({"user_id": user_id})
            from bson import ObjectId
            try:
                user_obj = ObjectId(user_id)
                await db.users.update_one(
                    {"_id": user_obj},
                    {"$set": {"tokens_revoked_before": now}}
                )
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"Error revoking all user sessions: {e}")

    log_security_event(
        event_code="AUTH_SESSIONS_REVOKED",
        action="revoke_all_user_sessions",
        status="SUCCESS",
        actor_id=user_id,
        details={"reason": reason}
    )

def clear_local_revocation_cache():
    """Testing helper to clear in-memory revocation records."""
    _local_revoked_jtis.clear()
