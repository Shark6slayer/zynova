import pytest
import time
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from unittest.mock import patch, MagicMock
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database.client import connect_to_database, close_database_connection, get_database
from app.core.security import create_access_token
from app.core.rate_limit import phone_verify_rate_limiter

TEST_AUTH_HEADERS = {}
TEST_USER_ID = "66123456789abcdef0123456"
TEST_USER_EMAIL = "karuppusamyc80@gmail.com"

@pytest.fixture(autouse=True)
async def setup_test_user():
    await connect_to_database()
    db = get_database()
    phone_verify_rate_limiter.clear()
    if db is not None:
        await db.users.delete_many({"_id": ObjectId(TEST_USER_ID)})
        await db.users.delete_many({"email": TEST_USER_EMAIL})
        await db.users.delete_many({"phone_number": "+919876543210"})
        await db.users.delete_many({"phone_number": "+919123456789"})

        await db.users.insert_one({
            "_id": ObjectId(TEST_USER_ID),
            "email": TEST_USER_EMAIL,
            "username": "karuppusamyc80",
            "full_name": "Karuppusamy C",
            "hashed_password": "dummy_hash_for_testing_purposes",
            "is_active": True,
            "is_verified": True,
            "is_phone_verified": False,
            "phone_verified": False,
            "connect_activated": False,
            "created_at": datetime.now(timezone.utc)
        })

    token = create_access_token({"sub": TEST_USER_ID, "email": TEST_USER_EMAIL})
    global TEST_AUTH_HEADERS
    TEST_AUTH_HEADERS = {"Authorization": f"Bearer {token}"}

    yield

    if db is not None:
        await db.users.delete_many({"_id": ObjectId(TEST_USER_ID)})
        await db.users.delete_many({"email": TEST_USER_EMAIL})
        await db.users.delete_many({"phone_number": "+919876543210"})
        await db.users.delete_many({"phone_number": "+919123456789"})

    await close_database_connection()


@pytest.mark.asyncio
async def test_phone_verify_success():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        now_epoch = time.time()
        mock_decoded = {
            "uid": "fb_uid_12345",
            "phone_number": "+919876543210",
            "auth_time": now_epoch - 30,  # 30 seconds ago
            "firebase": {
                "sign_in_provider": "phone"
            }
        }
        with patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded):
            resp = await client.post(
                "/api/v1/auth/phone/verify",
                json={"id_token": "valid_firebase_id_token_12345"},
                headers=TEST_AUTH_HEADERS
            )
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["status"] == "verified"
            assert data["phone_number"] == "+919876543210"
            assert data["is_phone_verified"] is True
            assert data["connect_activated"] is True

        # Verify DB document
        db = get_database()
        user = await db.users.find_one({"_id": ObjectId(TEST_USER_ID)})
        assert user["phone_number"] == "+919876543210"
        assert user["is_phone_verified"] is True
        assert user["phone_verified"] is True
        assert user["connect_activated"] is True
        assert user["phone_verified_at"] is not None


@pytest.mark.asyncio
async def test_phone_verify_invalid_or_revoked_token():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        with patch("firebase_admin.auth.verify_id_token", side_effect=Exception("Token is revoked or invalid")):
            resp = await client.post(
                "/api/v1/auth/phone/verify",
                json={"id_token": "revoked_or_invalid_id_token"},
                headers=TEST_AUTH_HEADERS
            )
            assert resp.status_code == 400
            assert resp.json()["detail"] == "Verification failed"


@pytest.mark.asyncio
async def test_phone_verify_old_auth_time():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        now_epoch = time.time()
        mock_decoded = {
            "uid": "fb_uid_12345",
            "phone_number": "+919876543210",
            "auth_time": now_epoch - 400,  # > 5 minutes ago
            "firebase": {
                "sign_in_provider": "phone"
            }
        }
        with patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded):
            resp = await client.post(
                "/api/v1/auth/phone/verify",
                json={"id_token": "old_auth_time_token"},
                headers=TEST_AUTH_HEADERS
            )
            assert resp.status_code == 400
            assert resp.json()["detail"] == "Verification failed"


@pytest.mark.asyncio
async def test_phone_verify_non_phone_provider():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        now_epoch = time.time()
        mock_decoded = {
            "uid": "fb_uid_12345",
            "phone_number": "+919876543210",
            "auth_time": now_epoch - 10,
            "firebase": {
                "sign_in_provider": "google.com"  # Not 'phone'
            }
        }
        with patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded):
            resp = await client.post(
                "/api/v1/auth/phone/verify",
                json={"id_token": "google_provider_token"},
                headers=TEST_AUTH_HEADERS
            )
            assert resp.status_code == 400
            assert resp.json()["detail"] == "Verification failed"


@pytest.mark.asyncio
async def test_phone_verify_non_91_country_code():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        now_epoch = time.time()
        mock_decoded = {
            "uid": "fb_uid_12345",
            "phone_number": "+14155552671",  # US number
            "auth_time": now_epoch - 10,
            "firebase": {
                "sign_in_provider": "phone"
            }
        }
        with patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded):
            resp = await client.post(
                "/api/v1/auth/phone/verify",
                json={"id_token": "us_phone_token"},
                headers=TEST_AUTH_HEADERS
            )
            assert resp.status_code == 400
            assert resp.json()["detail"] == "Verification failed"


@pytest.mark.asyncio
async def test_phone_verify_missing_phone_claim():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        now_epoch = time.time()
        mock_decoded = {
            "uid": "fb_uid_12345",
            "auth_time": now_epoch - 10,
            "firebase": {
                "sign_in_provider": "phone"
            }
        }
        with patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded):
            resp = await client.post(
                "/api/v1/auth/phone/verify",
                json={"id_token": "missing_phone_claim_token"},
                headers=TEST_AUTH_HEADERS
            )
            assert resp.status_code == 400
            assert resp.json()["detail"] == "Verification failed"


@pytest.mark.asyncio
async def test_phone_verify_duplicate_phone_number():
    db = get_database()
    other_user_id = "66111111111abcdef0111111"
    # An already verified user owns this number
    await db.users.insert_one({
        "_id": ObjectId(other_user_id),
        "email": "other_user@example.com",
        "username": "other_user",
        "phone_number": "+919876543210",
        "is_active": True,
        "is_verified": True,
        "is_phone_verified": True,
        "phone_verified": True
    })

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            now_epoch = time.time()
            mock_decoded = {
                "uid": "fb_uid_duplicate",
                "phone_number": "+919876543210",
                "auth_time": now_epoch - 10,
                "firebase": {
                    "sign_in_provider": "phone"
                }
            }
            with patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded):
                resp = await client.post(
                    "/api/v1/auth/phone/verify",
                    json={"id_token": "token_with_duplicate_phone"},
                    headers=TEST_AUTH_HEADERS
                )
                assert resp.status_code == 400
                assert resp.json()["detail"] == "Verification failed"
    finally:
        await db.users.delete_one({"_id": ObjectId(other_user_id)})


@pytest.mark.asyncio
async def test_unverified_holder_cannot_block_victim_verification():
    """Validates that an attacker setting victim's number unverified cannot block victim from verifying."""
    db = get_database()
    attacker_id = "66222222222abcdef0222222"
    # Attacker put victim's number as pending/unverified
    await db.users.insert_one({
        "_id": ObjectId(attacker_id),
        "email": "attacker@example.com",
        "username": "attacker_user",
        "pending_phone": "+919876543210",
        "phone_number": None,
        "is_active": True,
        "is_verified": True,
        "is_phone_verified": False,
        "phone_verified": False
    })

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            now_epoch = time.time()
            mock_decoded = {
                "uid": "fb_uid_victim",
                "phone_number": "+919876543210",
                "auth_time": now_epoch - 10,
                "firebase": {
                    "sign_in_provider": "phone"
                }
            }
            with patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded):
                resp = await client.post(
                    "/api/v1/auth/phone/verify",
                    json={"id_token": "victim_firebase_token"},
                    headers=TEST_AUTH_HEADERS
                )
                assert resp.status_code == 200
                assert resp.json()["status"] == "verified"
                assert resp.json()["phone_number"] == "+919876543210"

            # Check that victim is verified
            victim_doc = await db.users.find_one({"_id": ObjectId(TEST_USER_ID)})
            assert victim_doc["phone_number"] == "+919876543210"
            assert victim_doc["is_phone_verified"] is True

            # Check that attacker's claim was completely cleared via $unset
            attacker_doc = await db.users.find_one({"_id": ObjectId(attacker_id)})
            assert "phone_number" not in attacker_doc or attacker_doc["phone_number"] is None
            assert "pending_phone" not in attacker_doc or attacker_doc.get("pending_phone") is None
    finally:
        await db.users.delete_one({"_id": ObjectId(attacker_id)})


@pytest.mark.asyncio
async def test_verified_number_cannot_be_taken_by_second_user():
    """Validates that once a number is verified by user A, user B cannot verify and claim it."""
    db = get_database()
    owner_id = "66333333333abcdef0333333"
    # Legitimate owner has verified phone
    await db.users.insert_one({
        "_id": ObjectId(owner_id),
        "email": "owner@example.com",
        "username": "owner_user",
        "phone_number": "+919876543210",
        "phone": "+919876543210",
        "is_active": True,
        "is_verified": True,
        "is_phone_verified": True,
        "phone_verified": True,
        "connect_activated": True
    })

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            now_epoch = time.time()
            mock_decoded = {
                "uid": "fb_uid_intruder",
                "phone_number": "+919876543210",
                "auth_time": now_epoch - 10,
                "firebase": {
                    "sign_in_provider": "phone"
                }
            }
            with patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded):
                resp = await client.post(
                    "/api/v1/auth/phone/verify",
                    json={"id_token": "intruder_firebase_token"},
                    headers=TEST_AUTH_HEADERS
                )
                assert resp.status_code == 400
                assert resp.json()["detail"] == "Verification failed"

            # Owner's verified phone remains untouched
            owner_doc = await db.users.find_one({"_id": ObjectId(owner_id)})
            assert owner_doc["phone_number"] == "+919876543210"
            assert owner_doc["is_phone_verified"] is True
    finally:
        await db.users.delete_one({"_id": ObjectId(owner_id)})


@pytest.mark.asyncio
async def test_phone_verify_request_body_phone_ignored():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        now_epoch = time.time()
        mock_decoded = {
            "uid": "fb_uid_12345",
            "phone_number": "+919876543210",  # Token has this number
            "auth_time": now_epoch - 10,
            "firebase": {
                "sign_in_provider": "phone"
            }
        }
        with patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded):
            resp = await client.post(
                "/api/v1/auth/phone/verify",
                json={
                    "id_token": "token_with_verified_number",
                    "phone_number": "+919999999999"  # Attacker submits body phone, MUST be ignored!
                },
                headers=TEST_AUTH_HEADERS
            )
            assert resp.status_code == 200
            data = resp.json()
            assert data["phone_number"] == "+919876543210"

        db = get_database()
        user = await db.users.find_one({"_id": ObjectId(TEST_USER_ID)})
        assert user["phone_number"] == "+919876543210"


@pytest.mark.asyncio
async def test_phone_number_change_resets_verification():
    db = get_database()
    # First set user as verified with a phone number
    await db.users.update_one(
        {"_id": ObjectId(TEST_USER_ID)},
        {"$set": {
            "phone_number": "+919876543210",
            "phone": "+919876543210",
            "is_phone_verified": True,
            "phone_verified": True,
            "connect_activated": True,
            "phone_verified_at": datetime.now(timezone.utc)
        }}
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # User updates profile with a new phone number
        resp = await client.patch(
            "/api/v1/users/me",
            json={"phone_number": "+919123456789"},
            headers=TEST_AUTH_HEADERS
        )
        assert resp.status_code == 200

        # DB must now show phone verification has been reset, and unverified phone stored in pending_phone
        updated_user = await db.users.find_one({"_id": ObjectId(TEST_USER_ID)})
        assert updated_user.get("pending_phone") == "+919123456789"
        assert "phone_number" not in updated_user or updated_user.get("phone_number") is None
        assert "phone" not in updated_user or updated_user.get("phone") is None
        assert updated_user["is_phone_verified"] is False
        assert updated_user["phone_verified"] is False
        assert updated_user["connect_activated"] is False
        assert "phone_verified_at" not in updated_user or updated_user.get("phone_verified_at") is None


@pytest.mark.asyncio
async def test_phone_verify_rate_limit():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        now_epoch = time.time()
        mock_decoded = {
            "uid": "fb_uid_12345",
            "phone_number": "+919876543210",
            "auth_time": now_epoch - 10,
            "firebase": {
                "sign_in_provider": "phone"
            }
        }
        with patch("firebase_admin.auth.verify_id_token", return_value=mock_decoded):
            # Exhaust 5 requests
            for _ in range(5):
                resp = await client.post(
                    "/api/v1/auth/phone/verify",
                    json={"id_token": "valid_token"},
                    headers=TEST_AUTH_HEADERS
                )
                assert resp.status_code == 200

            # 6th request should hit rate limit
            resp6 = await client.post(
                "/api/v1/auth/phone/verify",
                json={"id_token": "valid_token"},
                headers=TEST_AUTH_HEADERS
            )
            assert resp6.status_code == 429


@pytest.mark.asyncio
async def test_connect_blocked_when_unverified_and_allowed_when_verified():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. When unverified:
        resp = await client.get("/api/v1/chat/conversations", headers=TEST_AUTH_HEADERS)
        assert resp.status_code == 403
        data = resp.json()
        assert data["detail"]["code"] == "PHONE_NOT_VERIFIED"

        # 2. When verified:
        db = get_database()
        await db.users.update_one(
            {"_id": ObjectId(TEST_USER_ID)},
            {"$set": {
                "phone_number": "+919876543210",
                "phone": "+919876543210",
                "is_phone_verified": True,
                "phone_verified": True,
                "connect_activated": True
            }}
        )

        resp_allowed = await client.get("/api/v1/chat/conversations", headers=TEST_AUTH_HEADERS)
        assert resp_allowed.status_code == 200


@pytest.mark.asyncio
async def test_phone_verify_no_auth_header():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/api/v1/auth/phone/verify",
            json={"id_token": "some_token"}
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_connect_status_reflects_phone_not_email():
    """Validates that GET /delivery/phone/status reflects is_phone_verified, NEVER email is_verified."""
    db = get_database()
    # User has email verified (is_verified: True), but phone unverified (is_phone_verified: False)
    await db.users.update_one(
        {"_id": ObjectId(TEST_USER_ID)},
        {"$set": {
            "is_verified": True,
            "is_phone_verified": False,
            "phone_verified": False,
            "connect_activated": False,
            "phone_number": None,
            "phone": None
        }}
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.get("/api/v1/delivery/phone/status", headers=TEST_AUTH_HEADERS)
        assert res.status_code == 200
        data = res.json()
        assert data["is_verified"] is False
        assert data["connect_activated"] is False

        # Now verify phone
        await db.users.update_one(
            {"_id": ObjectId(TEST_USER_ID)},
            {"$set": {
                "is_verified": True,
                "is_phone_verified": True,
                "phone_verified": True,
                "connect_activated": True,
                "phone_number": "+919876543210"
            }}
        )

        res2 = await client.get("/api/v1/delivery/phone/status", headers=TEST_AUTH_HEADERS)
        assert res2.status_code == 200
        data2 = res2.json()
        assert data2["is_verified"] is True
        assert data2["connect_activated"] is True


@pytest.mark.asyncio
async def test_delivery_route_cannot_pass_connect_phone_gate():
    """Validates that verifying phone via delivery endpoint sets delivery_phone_verified, NOT Connect flags."""
    db = get_database()
    # Reset user to unverified
    await db.users.update_one(
        {"_id": ObjectId(TEST_USER_ID)},
        {"$set": {
            "is_phone_verified": False,
            "phone_verified": False,
            "connect_activated": False,
            "delivery_phone_verified": False,
            "phone_number": None,
            "phone": None
        }}
    )

    # Insert delivery OTP record
    now = datetime.now(timezone.utc)
    await db.phone_otps.update_one(
        {"user_id": TEST_USER_ID, "phone": "+919876543210"},
        {"$set": {
            "user_id": TEST_USER_ID,
            "phone": "+919876543210",
            "otp_hash": "123456",
            "created_at": now,
            "expires_at": now + timedelta(minutes=10),
            "attempts": 0
        }},
        upsert=True
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Verify via delivery endpoint
        resp = await client.post(
            "/api/v1/delivery/phone/verify-otp",
            json={"phone_number": "+919876543210", "otp": "123456"},
            headers=TEST_AUTH_HEADERS
        )
        assert resp.status_code == 200

        # Check DB user document
        user = await db.users.find_one({"_id": ObjectId(TEST_USER_ID)})
        assert user.get("delivery_phone_verified") is True
        assert user.get("is_phone_verified") is False
        assert user.get("phone_verified") is False
        assert user.get("connect_activated") is False

        # Connect gate must still BLOCK this user!
        resp_gate = await client.get("/api/v1/chat/conversations", headers=TEST_AUTH_HEADERS)
        assert resp_gate.status_code == 403
        assert resp_gate.json()["detail"]["code"] == "PHONE_NOT_VERIFIED"


def test_chat_websocket_unverified_rejected():
    """Validates that an unverified phone user is closed on /ws with policy violation code 1008."""
    from starlette.testclient import TestClient
    from starlette.websockets import WebSocketDisconnect
    from unittest.mock import patch, AsyncMock, MagicMock

    token = create_access_token({"sub": TEST_USER_ID, "email": TEST_USER_EMAIL})
    client = TestClient(app)

    with patch("app.api.routes.chat.get_database") as mock_get_db:
        mock_db = MagicMock()
        mock_db.users.find_one = AsyncMock(return_value={
            "_id": ObjectId(TEST_USER_ID),
            "is_phone_verified": False,
            "phone_verified": False,
            "connect_activated": False
        })
        mock_get_db.return_value = mock_db

        with pytest.raises(WebSocketDisconnect) as exc_info:
            with client.websocket_connect(f"/api/v1/chat/ws?token={token}"):
                pass
        assert exc_info.value.code == 1008


def test_chat_websocket_verified_connects():
    """Validates that a verified phone user successfully connects to /ws."""
    from starlette.testclient import TestClient
    from unittest.mock import patch, AsyncMock, MagicMock

    token = create_access_token({"sub": TEST_USER_ID, "email": TEST_USER_EMAIL})
    client = TestClient(app)

    with patch("app.api.routes.chat.get_database") as mock_get_db:
        mock_db = MagicMock()
        mock_db.users.find_one = AsyncMock(return_value={
            "_id": ObjectId(TEST_USER_ID),
            "is_phone_verified": True,
            "phone_verified": True,
            "connect_activated": True,
            "phone_number": "+919876543210"
        })
        mock_get_db.return_value = mock_db

        with client.websocket_connect(f"/api/v1/chat/ws?token={token}") as ws:
            ws.send_text("ping")
            data = ws.receive_text()
            assert data == "pong"


@pytest.mark.asyncio
async def test_multiple_users_clearing_or_missing_phone_never_conflict():
    """
    Verifies that multiple users with unset or missing phone numbers never trigger DuplicateKeyError
    under the unique partial index on users.phone_number (partialFilterExpression: {"phone_number": {"$type": "string"}}).
    Also validates that updating profile phone uses $unset and doesn't store phone_number=None.
    """
    db = get_database()
    uid_a = str(ObjectId())
    uid_b = str(ObjectId())
    now = datetime.now(timezone.utc)

    import uuid
    rnd = uuid.uuid4().hex[:6]
    email_a = f"user_a_{rnd}@test.com"
    email_b = f"user_b_{rnd}@test.com"
    uname_a = f"user_a_{rnd}"
    uname_b = f"user_b_{rnd}"

    phone_test_a = f"+9198{rnd[:8]}"
    phone_test_b = f"+9197{rnd[:8]}"

    # Clean up before and after
    await db.users.delete_many({"email": {"$in": [email_a, email_b]}})
    await db.users.delete_many({"phone_number": {"$in": [phone_test_a, phone_test_b, f"+9196{rnd[:8]}"]}})

    # 1. Create two users with verified phone numbers first
    await db.users.insert_many([
        {
            "_id": ObjectId(uid_a),
            "email": email_a,
            "username": uname_a,
            "full_name": "User A",
            "phone_number": phone_test_a,
            "phone": phone_test_a,
            "is_phone_verified": True,
            "phone_verified": True,
            "created_at": now
        },
        {
            "_id": ObjectId(uid_b),
            "email": email_b,
            "username": uname_b,
            "full_name": "User B",
            "phone_number": phone_test_b,
            "phone": phone_test_b,
            "is_phone_verified": True,
            "phone_verified": True,
            "created_at": now
        }
    ])

    token_a = create_access_token({"sub": uid_a, "email": email_a})
    token_b = create_access_token({"sub": uid_b, "email": email_b})

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Both users change their phone number in profile
        resp_a = await client.patch(
            "/api/v1/users/me",
            json={"phone_number": "+919999900001"},
            headers={"Authorization": f"Bearer {token_a}"}
        )
        assert resp_a.status_code == 200

        resp_b = await client.patch(
            "/api/v1/users/me",
            json={"phone_number": "+919999900002"},
            headers={"Authorization": f"Bearer {token_b}"}
        )
        assert resp_b.status_code == 200

        # Verify documents in MongoDB have NO phone_number field (it was $unset, NOT set to null)
        doc_a = await db.users.find_one({"_id": ObjectId(uid_a)})
        doc_b = await db.users.find_one({"_id": ObjectId(uid_b)})

        assert "phone_number" not in doc_a
        assert "phone" not in doc_a
        assert doc_a.get("pending_phone") == "+919999900001"
        assert doc_a.get("is_phone_verified") is False

        assert "phone_number" not in doc_b
        assert "phone" not in doc_b
        assert doc_b.get("pending_phone") == "+919999900002"
        assert doc_b.get("is_phone_verified") is False

        # Now test that two verified users cannot hold the same phone number
        # Verify user_a with target phone
        target_dup_phone = f"+9196{rnd[:8]}"
        await db.users.update_one(
            {"_id": ObjectId(uid_a)},
            {"$set": {
                "phone_number": target_dup_phone,
                "is_phone_verified": True,
                "phone_verified": True
            }}
        )

        # Attempting to assign target_dup_phone to user_b directly must fail with DuplicateKeyError
        from pymongo.errors import DuplicateKeyError
        with pytest.raises(DuplicateKeyError):
            await db.users.update_one(
                {"_id": ObjectId(uid_b)},
                {"$set": {
                    "phone_number": target_dup_phone,
                    "is_phone_verified": True,
                    "phone_verified": True
                }}
            )

    # Cleanup test users
    await db.users.delete_many({"_id": {"$in": [ObjectId(uid_a), ObjectId(uid_b)]}})



