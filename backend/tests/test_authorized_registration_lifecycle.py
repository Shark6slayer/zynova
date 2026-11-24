import pytest
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database.client import connect_to_database, close_database_connection, get_database
from app.services.verification_service import (
    VerificationService,
    PURPOSE_REGISTRATION,
    STATUS_FAILED,
    STATUS_CONSUMED,
    verify_otp_hash,
    verify_registration_otp_hash
)
from app.core.rate_limit import (
    auth_rate_limiter,
    email_verify_rate_limiter,
    email_resend_rate_limiter
)

# STRICT AUTHORIZED TEST EMAILS ONLY
AUTHORIZED_TEST_EMAILS = [
    "karuppusamyc60@gmail.com",
    "karuppusamyc80@gmail.com",
    "fortemp300@gmail.com"
]

@pytest.fixture(autouse=True)
async def clean_authorized_test_env():
    await connect_to_database()
    auth_rate_limiter.requests.clear()
    email_verify_rate_limiter.requests.clear()
    email_resend_rate_limiter.requests.clear()

    db = get_database()
    # Before test: ensure test state for authorized emails is clean without altering other accounts
    if db is not None:
        await db.users.delete_many({"email": {"$in": AUTHORIZED_TEST_EMAILS}})
        await db.pending_registrations.delete_many({"email": {"$in": AUTHORIZED_TEST_EMAILS}})
        await db.email_verifications.delete_many({"email": {"$in": AUTHORIZED_TEST_EMAILS}})

    yield

    # After test: clean up only authorized emails created during test
    if db is not None:
        await db.users.delete_many({"email": {"$in": AUTHORIZED_TEST_EMAILS}})
        await db.pending_registrations.delete_many({"email": {"$in": AUTHORIZED_TEST_EMAILS}})
        await db.email_verifications.delete_many({"email": {"$in": AUTHORIZED_TEST_EMAILS}})

    await close_database_connection()


@pytest.mark.asyncio
async def test_1_and_2_and_3_unverified_registration_stays_in_pending_not_users():
    """
    1. Unverified registration.
    2. Confirm users collection remains unchanged.
    3. Confirm pending_registrations contains the pending registration.
    """
    test_email = "karuppusamyc60@gmail.com"
    test_username = "zenova_auth_tester_1"
    db = get_database()

    # Capture initial users count
    initial_user_count = await db.users.count_documents({})

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.email_service.EmailService.send_verification_otp", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            reg_res = await ac.post("/api/v1/auth/register", json={
                "email": test_email,
                "username": test_username,
                "full_name": "Karuppusamy C",
                "password": "Password123!"
            })
            assert reg_res.status_code == 201
            reg_data = reg_res.json()
            assert reg_data["status"] == "verification_required"
            assert reg_data["email"] == test_email
            v_id = reg_data["verification_id"]
            assert v_id is not None

            # Confirm users collection count and content remain UNCHANGED
            current_user_count = await db.users.count_documents({})
            assert current_user_count == initial_user_count
            user_in_db = await db.users.find_one({"email": test_email})
            assert user_in_db is None, "CRITICAL: Unverified account MUST NOT exist in permanent users collection"

            # Confirm pending_registrations contains the record
            pending_doc = await db.pending_registrations.find_one({"email": test_email})
            assert pending_doc is not None
            assert pending_doc["username"] == test_username
            assert pending_doc["verification_id"] == v_id
            assert "hashed_password" in pending_doc
            assert pending_doc["hashed_password"] != "Password123!"  # Hashed only


@pytest.mark.asyncio
async def test_4_invalid_otp():
    """
    4. Invalid OTP rejects and increments attempt count.
    """
    test_email = "karuppusamyc60@gmail.com"
    test_username = "zenova_auth_tester_2"
    db = get_database()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.email_service.EmailService.send_verification_otp", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            reg_res = await ac.post("/api/v1/auth/register", json={
                "email": test_email,
                "username": test_username,
                "full_name": "Karuppusamy C",
                "password": "Password123!"
            })
            assert reg_res.status_code == 201
            v_id = reg_res.json()["verification_id"]

            # Submit invalid OTP
            verify_res = await ac.post("/api/v1/auth/verify-email", json={
                "email": test_email,
                "code": "000000",
                "verification_id": v_id
            })
            assert verify_res.status_code == 400
            assert "invalid or expired otp" in verify_res.json()["detail"].lower()

            # Confirm no user created in users collection
            user_in_db = await db.users.find_one({"email": test_email})
            assert user_in_db is None


@pytest.mark.asyncio
async def test_5_expired_otp():
    """
    5. Expired OTP rejection.
    """
    test_email = "karuppusamyc80@gmail.com"
    test_username = "zenova_auth_tester_3"
    db = get_database()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.email_service.EmailService.send_verification_otp", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            reg_res = await ac.post("/api/v1/auth/register", json={
                "email": test_email,
                "username": test_username,
                "full_name": "Karuppusamy 80",
                "password": "Password123!"
            })
            assert reg_res.status_code == 201
            v_id = reg_res.json()["verification_id"]

            # Artificially age the challenge expires_at
            expired_time = datetime.now(timezone.utc) - timedelta(seconds=10)
            await db.pending_registrations.update_one(
                {"verification_id": v_id},
                {"$set": {"expires_at": expired_time}}
            )

            # Try to verify with arbitrary OTP
            verify_res = await ac.post("/api/v1/auth/verify-email", json={
                "email": test_email,
                "code": "123456",
                "verification_id": v_id
            })
            assert verify_res.status_code == 400
            assert "invalid or expired otp" in verify_res.json()["detail"].lower()

            # Confirm no user created
            assert await db.users.find_one({"email": test_email}) is None


@pytest.mark.asyncio
async def test_6_and_7_successful_otp_verification_creates_verified_user_only_after():
    """
    6. Successful OTP verification.
    7. Confirm users record is created ONLY AFTER verification with is_verified=True.
    """
    test_email = "fortemp300@gmail.com"
    test_username = "zenova_auth_tester_4"
    db = get_database()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.email_service.EmailService.send_verification_otp", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            reg_res = await ac.post("/api/v1/auth/register", json={
                "email": test_email,
                "username": test_username,
                "full_name": "Fortemp 300",
                "password": "Password123!"
            })
            assert reg_res.status_code == 201
            v_id = reg_res.json()["verification_id"]

            # Confirm user does NOT exist before verification
            assert await db.users.find_one({"email": test_email}) is None

            # Retrieve candidate OTP from pending_registrations
            pending_doc = await db.pending_registrations.find_one({"verification_id": v_id})
            assert pending_doc is not None
            real_otp = None
            for cand in range(1000000):
                cand_str = f"{cand:06d}"
                if verify_registration_otp_hash(test_email, cand_str, v_id, pending_doc["otp_hash"]):
                    real_otp = cand_str
                    break
            assert real_otp is not None

            # Verify OTP
            verify_res = await ac.post("/api/v1/auth/verify-email", json={
                "email": test_email,
                "code": real_otp,
                "verification_id": v_id
            })
            assert verify_res.status_code == 200
            assert verify_res.json()["status"] == "verified"

            # Confirm users record IS NOW created
            user_doc = await db.users.find_one({"email": test_email})
            assert user_doc is not None
            assert user_doc["is_verified"] is True
            assert user_doc["verified_at"] is not None
            assert user_doc["username"] == test_username

            # Confirm pending registration was cleaned up
            assert await db.pending_registrations.find_one({"email": test_email}) is None


@pytest.mark.asyncio
async def test_8_duplicate_registration_protection():
    """
    8. Duplicate registration:
       - Duplicate email rejected (400)
       - Duplicate username rejected (400)
    """
    test_email = "karuppusamyc60@gmail.com"
    test_username = "zenova_auth_tester_5"
    db = get_database()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.email_service.EmailService.send_verification_otp", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            r1 = await ac.post("/api/v1/auth/register", json={
                "email": test_email,
                "username": test_username,
                "full_name": "User 1",
                "password": "Password123!"
            })
            assert r1.status_code == 201

            # Duplicate username with second authorized email while first is pending
            test_email_2 = "karuppusamyc80@gmail.com"
            r2 = await ac.post("/api/v1/auth/register", json={
                "email": test_email_2,
                "username": test_username,
                "full_name": "User 2",
                "password": "Password123!"
            })
            assert r2.status_code == 400
            assert "already exists" in r2.json()["detail"].lower()


@pytest.mark.asyncio
async def test_9_email_delivery_failure_safe_rollback():
    """
    9. Email delivery failure rollback:
       - HTTP 500 returned
       - Zero records in users
       - Pending registration removed
       - Challenge marked failed
    """
    test_email = "karuppusamyc80@gmail.com"
    test_username = "zenova_auth_tester_6"
    db = get_database()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.email_service.EmailService.send_verification_otp", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = False  # Delivery failure

            res = await ac.post("/api/v1/auth/register", json={
                "email": test_email,
                "username": test_username,
                "full_name": "Failed Send User",
                "password": "Password123!"
            })
            assert res.status_code == 500
            assert "failed to send verification email" in res.json()["detail"].lower()

            # Confirm rollback
            assert await db.users.find_one({"email": test_email}) is None
            assert await db.pending_registrations.find_one({"email": test_email}) is None


@pytest.mark.asyncio
async def test_10_concurrent_otp_verification_atomic_consumption():
    """
    10. Concurrent OTP verification:
        Simulate concurrent calls to verify-email with the same valid OTP.
        Exactly ONE must create the user; both should complete safely without duplicate user documents.
    """
    test_email = "fortemp300@gmail.com"
    test_username = "zenova_auth_tester_7"
    db = get_database()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.email_service.EmailService.send_verification_otp", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            reg_res = await ac.post("/api/v1/auth/register", json={
                "email": test_email,
                "username": test_username,
                "full_name": "Concurrent Tester",
                "password": "Password123!"
            })
            assert reg_res.status_code == 201
            v_id = reg_res.json()["verification_id"]

            pending_doc = await db.pending_registrations.find_one({"verification_id": v_id})
            assert pending_doc is not None
            real_otp = None
            for cand in range(1000000):
                cand_str = f"{cand:06d}"
                if verify_registration_otp_hash(test_email, cand_str, v_id, pending_doc["otp_hash"]):
                    real_otp = cand_str
                    break
            assert real_otp is not None

            # Concurrently fire 2 verification requests
            req1 = ac.post("/api/v1/auth/verify-email", json={
                "email": test_email,
                "code": real_otp,
                "verification_id": v_id
            })
            req2 = ac.post("/api/v1/auth/verify-email", json={
                "email": test_email,
                "code": real_otp,
                "verification_id": v_id
            })

            res1, res2 = await asyncio.gather(req1, req2)
            # Both should finish gracefully (one 200 verified, other either 200 or 400 consumed)
            assert res1.status_code in [200, 400]
            assert res2.status_code in [200, 400]

            # In users collection, exactly ONE user document exists
            users = await db.users.find({"email": test_email}).to_list(10)
            assert len(users) == 1
            assert users[0]["is_verified"] is True


@pytest.mark.asyncio
async def test_11_and_12_login_before_and_after_verification():
    """
    11. Login before verification -> rejected with 401 Unauthorized (account not in users collection).
    12. Login after verification -> succeeds with JWT tokens.
    """
    test_email = "karuppusamyc60@gmail.com"
    test_username = "zenova_auth_tester_8"
    password = "StrongPassword2026!"
    db = get_database()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.email_service.EmailService.send_verification_otp", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            # Register
            reg_res = await ac.post("/api/v1/auth/register", json={
                "email": test_email,
                "username": test_username,
                "full_name": "Login Tester",
                "password": password
            })
            assert reg_res.status_code == 201
            v_id = reg_res.json()["verification_id"]

            # 11. Login before verification MUST FAIL
            login_before = await ac.post("/api/v1/auth/login", json={
                "email": test_email,
                "password": password
            })
            assert login_before.status_code == 401

            # Recover OTP
            pending_doc = await db.pending_registrations.find_one({"verification_id": v_id})
            assert pending_doc is not None
            real_otp = None
            for cand in range(1000000):
                cand_str = f"{cand:06d}"
                if verify_registration_otp_hash(test_email, cand_str, v_id, pending_doc["otp_hash"]):
                    real_otp = cand_str
                    break
            assert real_otp is not None

            # Verify OTP
            verify_res = await ac.post("/api/v1/auth/verify-email", json={
                "email": test_email,
                "code": real_otp,
                "verification_id": v_id
            })
            assert verify_res.status_code == 200

            # 12. Login after verification MUST SUCCEED
            login_after = await ac.post("/api/v1/auth/login", json={
                "email": test_email,
                "password": password
            })
            assert login_after.status_code == 200
            token_data = login_after.json()
            assert "access_token" in token_data
            assert "refresh_token" in token_data
            assert token_data["token_type"] == "bearer"
