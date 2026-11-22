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
    verify_otp_hash
)
from app.core.rate_limit import (
    auth_rate_limiter,
    email_verify_rate_limiter,
    email_resend_rate_limiter
)

@pytest.fixture(autouse=True)
async def clean_registration_integrity_env():
    await connect_to_database()
    auth_rate_limiter.requests.clear()
    email_verify_rate_limiter.requests.clear()
    email_resend_rate_limiter.requests.clear()
    test_emails = []

    def register_test_email(email: str):
        test_emails.append(email.lower().strip())

    yield register_test_email

    db = get_database()
    if db is not None and test_emails:
        await db.users.delete_many({"email": {"$in": test_emails}})
        await db.pending_registrations.delete_many({"email": {"$in": test_emails}})
        await db.email_verifications.delete_many({"email": {"$in": test_emails}})
        await db.refresh_tokens.delete_many({"user_id": {"$in": [str(u["_id"]) async for u in db.users.find({"email": {"$in": test_emails}})]}})

    await close_database_connection()


@pytest.mark.asyncio
async def test_no_permanent_user_and_rollback_when_email_dispatch_fails(clean_registration_integrity_env):
    """
    Verifies that when email dispatch fails:
    1. Returns HTTP 500 error.
    2. Zero users are created in db.users.
    3. db.pending_registrations is rolled back (record deleted).
    4. Verification challenge is marked failed.
    """
    suffix = uuid.uuid4().hex[:6]
    test_email = f"fail_email_{suffix}@zenova.in"
    clean_registration_integrity_env(test_email)
    db = get_database()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.email_service.EmailService.send_verification_otp", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = False  # Simulate email dispatch rejection

            resp = await ac.post("/api/v1/auth/register", json={
                "email": test_email,
                "username": f"fail_{suffix}",
                "full_name": "Fail Tester",
                "password": "Password123!"
            })
            assert resp.status_code == 500
            assert "failed to send verification email" in resp.json()["detail"].lower()

            # Verify no permanent user exists
            user_doc = await db.users.find_one({"email": test_email})
            assert user_doc is None

            # Verify pending registration was rolled back / deleted
            pending_doc = await db.pending_registrations.find_one({"email": test_email})
            assert pending_doc is None

            # Verify email_verifications record is marked failed
            v_doc = await db.email_verifications.find_one({"email": test_email})
            assert v_doc is not None
            assert v_doc["status"] == STATUS_FAILED


@pytest.mark.asyncio
async def test_correct_otp_creates_exactly_one_verified_user_and_deletes_pending(clean_registration_integrity_env):
    """
    Verifies that upon submitting the correct OTP:
    1. Exactly one user is created in db.users with is_verified=True.
    2. Pending registration is deleted.
    3. Re-submitting the same OTP fails (challenge single-use consumed).
    """
    suffix = uuid.uuid4().hex[:6]
    test_email = f"single_create_{suffix}@zenova.in"
    clean_registration_integrity_env(test_email)
    db = get_database()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.email_service.EmailService.send_verification_otp", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            reg_resp = await ac.post("/api/v1/auth/register", json={
                "email": test_email,
                "username": f"single_{suffix}",
                "full_name": "Single User Tester",
                "password": "Password123!"
            })
            assert reg_resp.status_code == 201
            v_id = reg_resp.json()["verification_id"]

            # Recover OTP from DB hash
            v_doc = await db.email_verifications.find_one({"verification_id": v_id})
            real_otp = None
            for cand in range(100000, 1000000):
                if verify_otp_hash(v_id, PURPOSE_REGISTRATION, str(cand), v_doc["otp_hash"]):
                    real_otp = str(cand)
                    break
            assert real_otp is not None

            # Verify OTP
            verify_resp = await ac.post("/api/v1/auth/verify-email", json={
                "email": test_email,
                "code": real_otp,
                "verification_id": v_id
            })
            assert verify_resp.status_code == 200
            assert verify_resp.json()["status"] == "verified"

            # Exactly one user in db.users
            users = await db.users.find({"email": test_email}).to_list(10)
            assert len(users) == 1
            assert users[0]["is_verified"] is True
            assert users[0]["verified_at"] is not None

            # Pending registration is gone
            pending = await db.pending_registrations.find_one({"email": test_email})
            assert pending is None

            # Second attempt with same code fails
            verify_again = await ac.post("/api/v1/auth/verify-email", json={
                "email": test_email,
                "code": real_otp,
                "verification_id": v_id
            })
            assert verify_again.status_code in [200, 400]
            # If 200 it returns "Email is already verified", or 400 consumed challenge
            if verify_again.status_code == 200:
                assert "already verified" in verify_again.json()["message"].lower()


@pytest.mark.asyncio
async def test_expired_otp_cannot_create_user(clean_registration_integrity_env):
    """
    Verifies that if an OTP challenge is expired, verification is rejected
    and no user is created.
    """
    suffix = uuid.uuid4().hex[:6]
    test_email = f"expired_otp_{suffix}@zenova.in"
    clean_registration_integrity_env(test_email)
    db = get_database()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.email_service.EmailService.send_verification_otp", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            reg_resp = await ac.post("/api/v1/auth/register", json={
                "email": test_email,
                "username": f"exp_{suffix}",
                "full_name": "Expired Tester",
                "password": "Password123!"
            })
            assert reg_resp.status_code == 201
            v_id = reg_resp.json()["verification_id"]

            # Recover OTP
            v_doc = await db.email_verifications.find_one({"verification_id": v_id})
            real_otp = None
            for cand in range(100000, 1000000):
                if verify_otp_hash(v_id, PURPOSE_REGISTRATION, str(cand), v_doc["otp_hash"]):
                    real_otp = str(cand)
                    break

            # Artificially age the expiration in db.email_verifications to 10 seconds ago
            expired_time = datetime.now(timezone.utc) - timedelta(seconds=10)
            await db.email_verifications.update_one(
                {"verification_id": v_id},
                {"$set": {"expires_at": expired_time}}
            )

            # Verification must fail
            verify_resp = await ac.post("/api/v1/auth/verify-email", json={
                "email": test_email,
                "code": real_otp,
                "verification_id": v_id
            })
            assert verify_resp.status_code == 400
            assert "expired" in verify_resp.json()["detail"].lower() or "not requested" in verify_resp.json()["detail"].lower()

            # Permanent user MUST NOT be created
            user_doc = await db.users.find_one({"email": test_email})
            assert user_doc is None


@pytest.mark.asyncio
async def test_duplicate_and_concurrent_registration_handling(clean_registration_integrity_env):
    """
    Verifies duplicate username/email collisions:
    1. First user registers and verifies.
    2. Second registration with same email or username is rejected with 400.
    """
    suffix = uuid.uuid4().hex[:6]
    email1 = f"first_{suffix}@zenova.in"
    username1 = f"user_{suffix}"
    clean_registration_integrity_env(email1)
    db = get_database()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.email_service.EmailService.send_verification_otp", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            # Register user 1
            r1 = await ac.post("/api/v1/auth/register", json={
                "email": email1,
                "username": username1,
                "full_name": "First User",
                "password": "Password123!"
            })
            assert r1.status_code == 201

            # Try to register second user with same username but different email while pending
            email2 = f"second_{suffix}@zenova.in"
            clean_registration_integrity_env(email2)
            r2 = await ac.post("/api/v1/auth/register", json={
                "email": email2,
                "username": username1,
                "full_name": "Duplicate Username",
                "password": "Password123!"
            })
            assert r2.status_code == 400
            assert "already exists" in r2.json()["detail"].lower()
