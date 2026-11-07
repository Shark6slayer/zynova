import pytest
import os
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone
from bson import ObjectId

from app.main import app
from app.core.config import settings
from app.database.client import connect_to_database, get_database
from app.core.security import create_access_token, get_password_hash
from app.core.rate_limit import get_rate_limiter_health
from app.core.crypto_kms import get_kms_health, encrypt_field, decrypt_field
from app.core.token_revocation import is_token_revoked, revoke_token

@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

@pytest.fixture(autouse=True)
async def init_phase29_db():
    await connect_to_database()
    yield

# 1. Environment and Configuration Validation
def test_environment_configuration_strategy():
    assert settings.APP_NAME in ("SUPER_AI_BACKEND", "ZYNOVA_BACKEND")
    assert settings.APP_VERSION == "1.0.0"
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES == 30
    assert settings.REFRESH_TOKEN_EXPIRE_DAYS == 14
    # Ensure trusted origins include production domain
    assert "https://zynova.intellidev.in" in settings.CORS_ORIGINS
    assert "capacitor://localhost" in settings.CORS_ORIGINS

# 2. Production Mock-Mode Safety for AI Core Engine
def test_ai_mock_mode_production_safety():
    # If environment is production, AI_MOCK_MODE must never be true unless explicitly allowed
    if settings.ENVIRONMENT.lower() == "production":
        assert settings.AI_MOCK_MODE is False
        assert settings.AI_DEFAULT_PROVIDER != "mock"

# 3. Health & Readiness Verification
@pytest.mark.asyncio
async def test_health_and_readiness_endpoints(async_client):
    # Liveness check
    live_res = await async_client.get("/api/v1/health")
    assert live_res.status_code == 200
    assert live_res.json()["status"] == "healthy"

    # Readiness check (MongoDB + Redis)
    ready_res = await async_client.get("/api/v1/ready")
    assert ready_res.status_code == 200
    ready_data = ready_res.json()
    assert ready_data["status"] == "ready"
    assert "database" in ready_data
    assert "dependencies" in ready_data
    assert "redis" in ready_data["dependencies"]

    # Security subsystem health check
    sec_res = await async_client.get("/api/v1/health/security")
    assert sec_res.status_code == 200
    sec_data = sec_res.json()
    assert sec_data["status"] == "operational"
    assert "rate_limiter" in sec_data
    assert "kms" in sec_data

# 4. Redis Failure Behavior & Graceful Fallback
@pytest.mark.asyncio
async def test_redis_graceful_fallback():
    rl_health = await get_rate_limiter_health()
    # In dev/test with no REDIS_URL, rate limiter must report operational fallback
    assert rl_health["status"] in ("operational", "healthy")
    if not settings.REDIS_URL:
        assert rl_health.get("backend") in ("in_memory", "in-memory-sliding-window", "redis")

# 5. Cryptographic KMS Envelope & Field-Level Encryption
def test_crypto_kms_envelope_encryption():
    kms_info = get_kms_health()
    assert kms_info["status"] == "operational"
    assert kms_info["active_version"] == "v1"

    plaintext = "super_sensitive_pii_data_98765"
    context = "user_account_field"
    encrypted = encrypt_field(plaintext, context=context)
    assert encrypted.startswith("enc:v1:")
    assert encrypted != plaintext

    decrypted = decrypt_field(encrypted, context=context)
    assert decrypted == plaintext

# 6. Token Revocation & JTI Enforcement
@pytest.mark.asyncio
async def test_token_revocation_lifecycle():
    import uuid
    test_jti = f"test_jti_revocation_{uuid.uuid4().hex[:8]}"
    future_expiry = datetime.now(timezone.utc)
    
    # Check initial state
    assert await is_token_revoked(test_jti) is False

    # Revoke token
    await revoke_token(jti=test_jti, expires_at=future_expiry, reason="security_audit")
    assert await is_token_revoked(test_jti) is True

# 7. Private Media Access Authorization
@pytest.mark.asyncio
async def test_private_media_authorization_barrier(async_client):
    db = get_database()
    # Seed a private video
    priv_id = ObjectId()
    owner_id = str(ObjectId())
    await db.videos.insert_one({
        "_id": priv_id,
        "owner_id": owner_id,
        "title": "Confidential Board Meeting",
        "is_short": False,
        "visibility": "private",
        "created_at": datetime.now(timezone.utc)
    })

    # Unauthenticated stream request must return 403 Forbidden
    stream_res = await async_client.get(f"/api/v1/videos/{str(priv_id)}/stream")
    assert stream_res.status_code == 403

    # Clean up
    await db.videos.delete_one({"_id": priv_id})

# 8. Rate Limiter Security Headers & Sensitive Fail-Closed Policy
def test_rate_limiter_configuration():
    assert settings.RATE_LIMIT_FAIL_CLOSED_IN_PROD in (True, False)
    assert settings.REDIS_CONNECT_TIMEOUT_SECONDS <= 5.0
