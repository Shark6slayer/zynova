import pytest
import hmac
import hashlib
import json
import base64
from httpx import AsyncClient, ASGITransport
from bson import ObjectId
from datetime import datetime, timezone, timedelta

from app.main import app
from app.core.config import settings
from app.core.security import create_access_token
from app.core.crypto_kms import encrypt_field, decrypt_field
from app.services.meta_instagram_service import MetaInstagramService
from app.database.client import connect_to_database, close_database_connection, get_database

TEST_USER_ID = "6af9b2f3a9f38b086b92dde3"

@pytest.fixture(autouse=True)
async def setup_test_context():
    await connect_to_database()
    db = get_database()
    if db is not None:
        user_doc = {
            "_id": ObjectId(TEST_USER_ID),
            "email": "meta_ig_user@superai.in",
            "username": "meta_ig_user",
            "full_name": "Meta IG Tester"
        }
        await db.users.update_one({"_id": user_doc["_id"]}, {"$set": user_doc}, upsert=True)
    yield
    if db is not None:
        await db.instagram_connections.delete_many({"user_id": TEST_USER_ID})
        await db.posts.delete_many({"author_id": TEST_USER_ID, "source": "instagram"})
    await close_database_connection()

@pytest.fixture
def auth_headers():
    token = create_access_token({"sub": TEST_USER_ID, "email": "meta_ig_user@superai.in"})
    return {"Authorization": f"Bearer {token}"}

# ---------------------------------------------------------------------------
# 1. State Lifecycle: Secrets token, store in Redis, atomic get+delete
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_state_lifecycle():
    state = "test_state_secret_12345"
    user_id = TEST_USER_ID
    platform = "android"

    await MetaInstagramService.store_state(state, user_id, platform)
    
    # First atomic get+delete succeeds
    retrieved = await MetaInstagramService.get_and_delete_state(state)
    assert retrieved is not None
    assert retrieved["user_id"] == user_id
    assert retrieved["platform"] == platform

    # Second atomic get+delete returns None (preventing replay)
    second_attempt = await MetaInstagramService.get_and_delete_state(state)
    assert second_attempt is None

# ---------------------------------------------------------------------------
# 2. Crypto KMS: Envelope encryption & decryption round-trip
# ---------------------------------------------------------------------------

def test_kms_envelope_roundtrip():
    secret_token = "EAABwzLIXgn4BA...mock_permanent_page_token"
    context = f"ig_page_token:{TEST_USER_ID}"

    encrypted = encrypt_field(secret_token, context=context)
    assert encrypted.startswith("enc:")
    assert secret_token not in encrypted

    decrypted = decrypt_field(encrypted, context=context)
    assert decrypted == secret_token

    # Verify context mismatch rejection
    with pytest.raises(Exception):
        decrypt_field(encrypted, context="wrong_context")

# ---------------------------------------------------------------------------
# 3. Webhook Signature Validation (Valid & Invalid)
# ---------------------------------------------------------------------------

def test_webhook_signature_validation(monkeypatch):
    test_secret = "test_meta_app_secret_12345"
    monkeypatch.setattr(settings, "META_APP_SECRET", test_secret)

    raw_body = b'{"object": "instagram", "entry": []}'
    valid_sig = "sha256=" + hmac.new(test_secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    invalid_sig = "sha256=0000000000000000000000000000000000000000000000000000000000000000"

    assert MetaInstagramService.verify_hub_signature(raw_body, valid_sig) is True
    assert MetaInstagramService.verify_hub_signature(raw_body, invalid_sig) is False
    assert MetaInstagramService.verify_hub_signature(raw_body, None) is False

# ---------------------------------------------------------------------------
# 4. Signed Request Parsing (Deauthorize & Data-Deletion)
# ---------------------------------------------------------------------------

def test_signed_request_parsing(monkeypatch):
    test_secret = "test_meta_app_secret_12345"
    monkeypatch.setattr(settings, "META_APP_SECRET", test_secret)

    payload = {"algorithm": "HMAC-SHA256", "user_id": "meta_page_id_999", "issued_at": 1794750000}
    payload_json = json.dumps(payload).encode("utf-8")
    payload_b64 = base64.urlsafe_b64encode(payload_json).decode("utf-8").rstrip("=")

    expected_sig = hmac.new(test_secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(expected_sig).decode("utf-8").rstrip("=")

    valid_signed_request = f"{sig_b64}.{payload_b64}"
    parsed = MetaInstagramService.parse_signed_request(valid_signed_request)
    assert parsed is not None
    assert parsed["user_id"] == "meta_page_id_999"

    # Invalid signature test
    invalid_signed_request = f"invalid_signature.{payload_b64}"
    assert MetaInstagramService.parse_signed_request(invalid_signed_request) is None

# ---------------------------------------------------------------------------
# 5. Mobile Contract Verification: Routes & Shapes Match Contract Exactly
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_authorize_url_route(auth_headers, monkeypatch):
    monkeypatch.setattr(settings, "META_APP_ID", "123456789")
    monkeypatch.setattr(settings, "META_APP_SECRET", "mock_secret")
    
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/instagram/authorize-url?platform=android", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert "url" in data
        assert "https://www.facebook.com/v21.0/dialog/oauth" in data["url"]
        assert "scope=instagram_basic,instagram_manage_insights,pages_show_list,pages_read_engagement" in data["url"]

@pytest.mark.asyncio
async def test_get_status_route_contract(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Default: not_connected
        res = await client.get("/api/v1/instagram/status", headers=auth_headers)
        assert res.status_code == 200
        data = res.json()
        assert data == {
            "connected": False,
            "username": None,
            "status": "not_connected",
            "last_synced_at": None,
            "media_count": None
        }

@pytest.mark.asyncio
async def test_callback_mobile_redirect():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # User cancel/deny callback
        res = await client.get(
            "/api/v1/instagram/callback?error=access_denied&error_description=Permissions+denied",
            follow_redirects=False
        )
        assert res.status_code == 302
        loc = res.headers.get("location")
        assert loc.startswith("zenova://oauth/instagram?status=error&error=access_denied")

@pytest.mark.asyncio
async def test_duplicate_import_skipped(auth_headers):
    db = get_database()
    # Mock connected account
    enc_token = encrypt_field("mock_page_token", context=f"ig_page_token:{TEST_USER_ID}")
    await db.instagram_connections.insert_one({
        "user_id": TEST_USER_ID,
        "ig_user_id": "ig_123",
        "ig_username": "ig_creator",
        "page_id": "page_456",
        "access_token_enc": enc_token,
        "token_expires_at": datetime.now(timezone.utc) + timedelta(days=60),
        "status": "active"
    })

    # Pre-insert a post with instagram_media_id = "ig_media_001"
    await db.posts.insert_one({
        "author_id": TEST_USER_ID,
        "content": "Existing imported post",
        "source": "instagram",
        "instagram_media_id": "ig_media_001",
        "created_at": datetime.now(timezone.utc)
    })

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/instagram/import",
            json={"media_ids": ["ig_media_001"]},
            headers=auth_headers
        )
        assert res.status_code == 200
        data = res.json()
        assert len(data["results"]) == 1
        item = data["results"][0]
        assert item["id"] == "ig_media_001"
        assert item["status"] == "skipped"
        assert item["message"] == "Already imported"

@pytest.mark.asyncio
async def test_disconnect_route(auth_headers):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.delete("/api/v1/instagram/disconnect", headers=auth_headers)
        assert res.status_code == 200
        assert res.json() == {"ok": True}
