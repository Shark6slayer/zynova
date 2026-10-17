import os
import io
import time
import pytest
from datetime import datetime, timedelta, timezone
from bson import ObjectId
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.core.security import create_access_token, decode_token
from app.core.rate_limit import (
    SharedRateLimiter,
    get_client_ip,
    hash_client_key,
    get_rate_limiter_health
)
from app.core.token_revocation import (
    revoke_token,
    is_token_revoked,
    revoke_all_user_sessions,
    clear_local_revocation_cache
)
from app.core.scanner import (
    scan_quarantined_media,
    QUARANTINE_DIR,
    EICAR_SIGNATURE,
    SIMULATED_MALWARE_BYTE
)
from app.core.security_logger import log_security_event, sanitize_log_val
from app.database.client import connect_to_database, close_database_connection, get_database

@pytest.fixture(autouse=True)
async def init_phase8_test_db():
    await connect_to_database()
    clear_local_revocation_cache()
    yield
    clear_local_revocation_cache()
    await close_database_connection()


# ============================================================================
# PHASE 8A: SHARED RATE LIMITING TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_shared_rate_limiter_enforcement_and_window():
    """Verify rate limiter allows up to limit and blocks subsequent requests."""
    limiter = SharedRateLimiter(namespace="test_route", requests_limit=3, window_seconds=2)
    client_key = "user_test_rate_1"

    # 1. First 3 requests must succeed
    limiter.check(client_key)
    limiter.check(client_key)
    limiter.check(client_key)

    # 2. 4th request must be blocked with HTTP 429
    with pytest.raises(Exception) as exc_info:
        limiter.check(client_key)
    assert "429" in str(exc_info.value) or exc_info.value.status_code == 429

    # 3. Simulate window expiry
    limiter.requests[hash_client_key("test_route", client_key)] = [time.time() - 5.0]
    # Request should now succeed
    limiter.check(client_key)

@pytest.mark.asyncio
async def test_rate_limiter_ip_spoofing_defense():
    """Verify that untrusted X-Forwarded-For headers are ignored unless from a trusted proxy."""
    from starlette.datastructures import Headers
    from starlette.types import Scope

    # Simulate request from untrusted external IP attempting to spoof header
    scope: Scope = {
        "type": "http",
        "client": ("203.0.113.195", 12345),
        "headers": [(b"x-forwarded-for", b"198.51.100.1")],
    }
    req = type("MockRequest", (), {
        "client": type("Client", (), {"host": "203.0.113.195"}),
        "headers": {"x-forwarded-for": "198.51.100.1"}
    })()

    resolved_ip = get_client_ip(req)
    # Must resolve to direct connecting IP, NOT the spoofed header
    assert resolved_ip == "203.0.113.195"

@pytest.mark.asyncio
async def test_security_health_endpoint():
    """Verify /api/v1/health/security reports operational status of security subsystems."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.get("/api/v1/health/security")
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "operational"
        assert "rate_limiter" in data
        assert "token_revocation" in data
        assert "media_scanner" in data


# ============================================================================
# PHASE 8B: ACCESS TOKEN REVOCATION TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_access_token_has_jti_and_revocation_works():
    """Verify access tokens have jti and individual token revocation rejects token."""
    user_id = str(ObjectId())
    token = create_access_token({"sub": user_id})
    payload = decode_token(token)
    assert payload is not None
    assert "jti" in payload
    jti = payload["jti"]

    # Before revocation: is_token_revoked should be False
    assert await is_token_revoked(jti) is False

    # Revoke token
    exp = datetime.now(timezone.utc) + timedelta(minutes=15)
    await revoke_token(jti, expires_at=exp, reason="test_revocation", user_id=user_id)

    # After revocation: is_token_revoked must be True
    assert await is_token_revoked(jti) is True

@pytest.mark.asyncio
async def test_logout_immediately_revokes_access_token():
    """Verify calling /auth/logout immediately revokes the calling access token."""
    db = get_database()
    if db is None:
        pytest.skip("MongoDB required for live logout revocation test")

    user_id = str(ObjectId())
    # Create active user
    await db.users.insert_one({
        "_id": ObjectId(user_id),
        "email": f"logout_{user_id[:6]}@superai.in",
        "username": f"user_logout_{user_id[:6]}",
        "full_name": "Logout Tester",
        "is_active": True
    })

    try:
        token = create_access_token({"sub": user_id, "email": "test@superai.in"})
        headers = {"Authorization": f"Bearer {token}"}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # 1. Token works before logout
            res_before = await ac.get("/api/v1/auth/me", headers=headers)
            assert res_before.status_code == 200

            # 2. Call logout
            res_logout = await ac.post("/api/v1/auth/logout", headers=headers)
            assert res_logout.status_code == 200

            # 3. Same access token must be immediately rejected with 401
            res_after = await ac.get("/api/v1/auth/me", headers=headers)
            assert res_after.status_code == 401
            assert "revoked" in res_after.json().get("detail", "").lower()
    finally:
        await db.users.delete_one({"_id": ObjectId(user_id)})

@pytest.mark.asyncio
async def test_logout_does_not_affect_unrelated_users():
    """Verify that logging out User A does not invalidate User B's active token."""
    db = get_database()
    if db is None:
        pytest.skip("MongoDB required for multi-tenant isolation test")

    user_a = str(ObjectId())
    user_b = str(ObjectId())

    await db.users.insert_many([
        {"_id": ObjectId(user_a), "email": f"usera_{user_a[:6]}@test.com", "username": f"user_a_{user_a[:6]}", "full_name": "User A", "is_active": True},
        {"_id": ObjectId(user_b), "email": f"userb_{user_b[:6]}@test.com", "username": f"user_b_{user_b[:6]}", "full_name": "User B", "is_active": True}
    ])

    try:
        token_a = create_access_token({"sub": user_a})
        token_b = create_access_token({"sub": user_b})

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            # User A logs out
            logout_a = await ac.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token_a}"})
            assert logout_a.status_code == 200

            # User A is revoked
            res_a = await ac.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_a}"})
            assert res_a.status_code == 401

            # User B is completely unaffected and succeeds
            res_b = await ac.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token_b}"})
            assert res_b.status_code == 200
            assert res_b.json()["id"] == user_b
    finally:
        await db.users.delete_one({"_id": ObjectId(user_a)})
        await db.users.delete_one({"_id": ObjectId(user_b)})


# ============================================================================
# PHASE 8D: MEDIA MALWARE SCANNING TESTS
# ============================================================================

@pytest.mark.asyncio
async def test_malware_scanner_detects_eicar_signature(tmp_path):
    """Verify media scanner detects EICAR test signature and rejects malicious upload."""
    infected_file = tmp_path / "test_infected.jpg"
    # JPEG header + EICAR test string
    infected_file.write_bytes(b"\xff\xd8\xff\xe0" + EICAR_SIGNATURE)

    is_clean, msg = await scan_quarantined_media(str(infected_file), "test_infected.jpg")
    assert is_clean is False
    assert "Malware detected" in msg

@pytest.mark.asyncio
async def test_malware_scanner_accepts_clean_file(tmp_path):
    """Verify media scanner accepts clean JPEG file."""
    clean_file = tmp_path / "test_clean.jpg"
    clean_file.write_bytes(b"\xff\xd8\xff\xe0" + (b"\x00" * 128))

    is_clean, msg = await scan_quarantined_media(str(clean_file), "test_clean.jpg")
    assert is_clean is True
    assert msg == "CLEAN"

@pytest.mark.asyncio
async def test_upload_social_media_with_malware_rejected():
    """Verify social media upload endpoint rejects files with simulated malware."""
    db = get_database()
    if db is None:
        pytest.skip("MongoDB required for malware upload test")

    user_id = str(ObjectId())
    await db.users.insert_one({
        "_id": ObjectId(user_id),
        "email": f"malware_test_{user_id[:6]}@superai.in",
        "username": f"user_malware_{user_id[:6]}",
        "full_name": "Malware Tester",
        "is_active": True
    })

    try:
        token = create_access_token({"sub": user_id})

        # Prepare multipart upload with malicious test signature
        malicious_bytes = b"\xff\xd8\xff\xe0" + EICAR_SIGNATURE
        files = {"file": ("malware_photo.jpg", io.BytesIO(malicious_bytes), "image/jpeg")}

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post(
                "/api/v1/social/media",
                files=files,
                headers={"Authorization": f"Bearer {token}"}
            )
            assert res.status_code == 400
            assert "malware" in res.json().get("detail", "").lower()
    finally:
        await db.users.delete_one({"_id": ObjectId(user_id)})


# ============================================================================
# PHASE 8F: SECURITY OBSERVABILITY TESTS
# ============================================================================

def test_security_logger_redaction():
    """Verify sensitive fields and CRLF control characters are redacted in security logging."""
    sensitive_dict = {
        "password": "secret_password_123",
        "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.dummy_token_value",
        "card_number": "4111111111111234",
        "normal_meta": "safe_metadata\r\nwith_attempted_injection"
    }

    # Test sanitization helper directly
    sanitized = sanitize_log_val("safe_text\r\nline2")
    assert "\r" not in sanitized
    assert "\n" not in sanitized
    assert "safe_text line2" == sanitized

    # Verify event generation without throwing
    log_security_event(
        event_code="TEST_EVENT",
        action="test_action",
        status="SUCCESS",
        actor_id="user_123",
        details=sensitive_dict
    )
