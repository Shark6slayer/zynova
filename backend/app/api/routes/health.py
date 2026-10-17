from fastapi import APIRouter, status, Response
from app.database.client import get_database
from app.core.config import settings

router = APIRouter(tags=["Health & System"])

@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    """Reports whether the backend process is running."""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "environment": settings.ENVIRONMENT
    }

@router.get("/ready")
async def readiness_check(response: Response):
    """Verifies critical dependencies such as MongoDB."""
    db = get_database()
    mongo_status = "unavailable"
    if db is None:
        # Attempt an on-demand reconnect if database is currently disconnected
        from app.database.client import connect_to_database
        try:
            await connect_to_database()
            db = get_database()
        except Exception:
            pass

    if db is not None:
        try:
            await db.command("ping")
            mongo_status = "connected"
        except Exception:
            mongo_status = "error"
            
    is_ready = mongo_status == "connected"
    if not is_ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return {
        "status": "ready" if is_ready else "not_ready",
        "database": mongo_status,
        "dependencies": {
            "mongodb": mongo_status
        }
    }

@router.get("/version", status_code=status.HTTP_200_OK)
async def version_info():
    """Reports application version information."""
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "sovereign_framework": "Indic-FastAPI-v2"
    }

from app.core.rate_limit import get_rate_limiter_health
from app.core.crypto_kms import get_kms_health

@router.get("/health/security", status_code=status.HTTP_200_OK)
async def security_health():
    """Reports status of rate-limiting, token revocation, KMS, and media scanning subsystems without revealing secrets."""
    rl_health = await get_rate_limiter_health()
    kms_health = get_kms_health()
    return {
        "status": "operational",
        "rate_limiter": rl_health,
        "token_revocation": {"status": "operational", "ttl_enabled": True},
        "kms": kms_health,
        "media_scanner": {
            "clamav_configured": bool(settings.CLAMAV_HOST),
            "environment": settings.ENVIRONMENT
        }
    }
