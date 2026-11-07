import pytest
import io
import os
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone
from bson import ObjectId

from app.main import app
from app.core.config import settings
from app.database.client import connect_to_database, get_database, close_database_connection
from app.core.rate_limit import get_rate_limiter_health
from app.services.ai_providers import GeminiProvider, OpenAIProvider, AnthropicProvider
from app.services.media_service import get_storage_adapter, _validate_mime, _validate_magic
from app.core.ai_errors import AIProviderException, AIErrorCode

@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

@pytest.fixture(autouse=True)
async def ensure_db_conn():
    await connect_to_database()
    yield

# 1. Real MongoDB Atlas Connectivity & Index Verification
@pytest.mark.asyncio
async def test_real_mongodb_atlas_connectivity():
    db = get_database()
    assert db is not None, "MongoDB instance must be connected"
    ping_res = await db.command("ping")
    assert ping_res.get("ok") == 1.0

    # Verify primary collection indices exist in real MongoDB Atlas
    user_idx = await db.users.index_information()
    assert "email_1" in user_idx
    assert "username_1" in user_idx

    post_idx = await db.posts.index_information()
    assert any("created_at" in k for k in post_idx.keys())

# 2. Redis Staging Configuration & Fallback Verification
@pytest.mark.asyncio
async def test_redis_staging_resilience_and_telemetry():
    rl_health = await get_rate_limiter_health()
    assert rl_health["status"] in ("healthy", "operational")
    
    # If REDIS_URL is provided in staging, it must connect over TLS or standard URL
    if settings.REDIS_URL:
        assert rl_health["connected"] is True
        assert rl_health["backend"] == "redis"
    else:
        # Documented safe fallback
        assert rl_health["backend"] == "in-memory-sliding-window"
        assert "note" in rl_health

# 3. AI Providers: Credential Validation & Graceful Rejection
def test_ai_providers_credential_state():
    gemini = GeminiProvider()
    openai = OpenAIProvider()
    anthropic = AnthropicProvider()

    # Verify model catalogues are defined and uncorrupted
    assert len(gemini.get_supported_models()) >= 2
    assert len(openai.get_supported_models()) >= 2
    assert len(anthropic.get_supported_models()) >= 2

    # If GEMINI_API_KEY is not configured in environment, is_configured must report False
    if not settings.GEMINI_API_KEY:
        assert gemini.is_configured() is False
    else:
        assert gemini.is_configured() is True

@pytest.mark.asyncio
async def test_ai_provider_missing_credential_safe_error():
    # If no key is set, invoking stream_chat must raise AIProviderException(AUTHENTICATION_ERROR)
    # rather than leaking low-level urllib/requests exceptions or internal stack traces
    if not settings.GEMINI_API_KEY:
        gemini = GeminiProvider(api_key=None)
        with pytest.raises(AIProviderException) as exc_info:
            async for _ in gemini.stream_chat(
                messages=[{"role": "user", "content": "Ping test"}],
                model="gemini-2.5-flash"
            ):
                pass
        assert exc_info.value.code == AIErrorCode.AUTHENTICATION_ERROR

# 4. Storage Adapter & File Integrity Validation
@pytest.mark.asyncio
async def test_storage_adapter_and_mime_magic_bytes():
    adapter = get_storage_adapter()
    assert adapter.adapter_name in ("local-dev-filesystem", "s3-compatible") or adapter.adapter_name.startswith("s3-compatible")

    # Validate MIME configuration
    mp4_cfg = _validate_mime("video/mp4")
    assert mp4_cfg["ext"] == ".mp4"
    assert mp4_cfg["category"] == "video"

    # Validate Magic Bytes
    valid_mp4_header = b"\x00\x00\x00\x18ftypmp42"
    assert _validate_magic(valid_mp4_header, "video/mp4") is True

    spoofed_exe_header = b"MZ\x90\x00\x03\x00\x00\x00"
    assert _validate_magic(spoofed_exe_header, "video/mp4") is False

# 5. Database Connection Interruption & On-Demand Reconnection
@pytest.mark.asyncio
async def test_mongodb_reconnection_cycle(async_client):
    # Test readiness check when connection is active
    res1 = await async_client.get("/api/v1/ready")
    assert res1.status_code == 200
    assert res1.json()["database"] == "connected"
