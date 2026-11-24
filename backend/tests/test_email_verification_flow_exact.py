import pytest
import uuid
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database.client import connect_to_database, close_database_connection, get_database
from app.services.verification_service import verify_registration_otp_hash
from app.core.rate_limit import (
    auth_rate_limiter,
    email_verify_rate_limiter,
    email_resend_rate_limiter
)

AUTHORISED_TEST_EMAILS = [
    "karuppusamyc60@gmail.com",
    "karuppusamyc80@gmail.com",
    "fortemp300@gmail.com"
]

@pytest.fixture(autouse=True)
async def clean_env():
    await connect_to_database()
    auth_rate_limiter.requests.clear()
    email_verify_rate_limiter.requests.clear()
    email_resend_rate_limiter.requests.clear()

    db = get_database()
    if db is not None:
        await db.users.delete_many({"email": {"$in": AUTHORISED_TEST_EMAILS}})
        await db.pending_registrations.delete_many({"email": {"$in": AUTHORISED_TEST_EMAILS}})
        await db.email_verifications.delete_many({"email": {"$in": AUTHORISED_TEST_EMAILS}})

    yield

    if db is not None:
        await db.users.delete_many({"email": {"$in": AUTHORISED_TEST_EMAILS}})
        await db.pending_registrations.delete_many({"email": {"$in": AUTHORISED_TEST_EMAILS}})
        await db.email_verifications.delete_many({"email": {"$in": AUTHORISED_TEST_EMAILS}})

    await close_database_connection()


@pytest.mark.asyncio
async def test_email_verification_success():
    """Validates successful registration, OTP delivery, verification, and user activation."""
    test_email = "karuppusamyc60@gmail.com"
    db = get_database()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.email_service.EmailService.send_verification_otp", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            # Register
            reg_resp = await ac.post("/api/v1/auth/register", json={
                "email": test_email,
                "username": "zenova_success_user",
                "full_name": "Success User",
                "password": "Password123!"
            })
            assert reg_resp.status_code == 201
            reg_json = reg_resp.json()
            assert reg_json["expires_in_seconds"] == 600

            # Users collection MUST be empty of this user
            assert await db.users.find_one({"email": test_email}) is None

            # Pending record must contain hash, attempts=0, expires_at
            pending = await db.pending_registrations.find_one({"email": test_email})
            assert pending is not None
            assert pending["attempts"] == 0
            assert "otp_hash" in pending
            v_id = pending["verification_id"]

            # Recover OTP by candidate search against HMAC
            real_otp = None
            for cand in range(0, 1_000_000):
                cand_str = f"{cand:06d}"
                if verify_registration_otp_hash(test_email, cand_str, v_id, pending["otp_hash"]):
                    real_otp = cand_str
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

            # Pending registration deleted
            assert await db.pending_registrations.find_one({"email": test_email}) is None

            # User created in users with is_verified=True, verified_at=now
            user = await db.users.find_one({"email": test_email})
            assert user is not None
            assert user["is_verified"] is True
            assert user["verified_at"] is not None


@pytest.mark.asyncio
async def test_wrong_otp_increments_attempts():
    """Validates that a wrong OTP increments attempts and returns generic 'Invalid or expired OTP'."""
    test_email = "karuppusamyc60@gmail.com"
    db = get_database()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.email_service.EmailService.send_verification_otp", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            await ac.post("/api/v1/auth/register", json={
                "email": test_email,
                "username": "zenova_wrong_otp",
                "full_name": "Wrong OTP User",
                "password": "Password123!"
            })

            # Submit wrong OTP
            res = await ac.post("/api/v1/auth/verify-email", json={
                "email": test_email,
                "code": "000000"
            })
            assert res.status_code == 400
            assert res.json()["detail"] == "Invalid or expired OTP"

            # Check attempts incremented in pending_registrations
            pending = await db.pending_registrations.find_one({"email": test_email})
            assert pending is not None
            assert pending["attempts"] == 1

            # Users collection remains empty
            assert await db.users.find_one({"email": test_email}) is None


@pytest.mark.asyncio
async def test_expired_otp_deletes_pending_record():
    """Validates that an expired OTP deletes the pending record and rejects verification."""
    test_email = "karuppusamyc80@gmail.com"
    db = get_database()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.email_service.EmailService.send_verification_otp", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            await ac.post("/api/v1/auth/register", json={
                "email": test_email,
                "username": "zenova_expired_user",
                "full_name": "Expired User",
                "password": "Password123!"
            })

            # Age expires_at in pending_registrations
            past = datetime.now(timezone.utc) - timedelta(seconds=10)
            await db.pending_registrations.update_one(
                {"email": test_email},
                {"$set": {"expires_at": past}}
            )

            res = await ac.post("/api/v1/auth/verify-email", json={
                "email": test_email,
                "code": "123456"
            })
            assert res.status_code == 400
            assert res.json()["detail"] == "Invalid or expired OTP"

            # Pending record must be deleted
            assert await db.pending_registrations.find_one({"email": test_email}) is None
            assert await db.users.find_one({"email": test_email}) is None


@pytest.mark.asyncio
async def test_reused_otp_rejected():
    """Validates that an OTP cannot be reused after successful verification."""
    test_email = "fortemp300@gmail.com"
    db = get_database()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.email_service.EmailService.send_verification_otp", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            await ac.post("/api/v1/auth/register", json={
                "email": test_email,
                "username": "zenova_reused_user",
                "full_name": "Reused User",
                "password": "Password123!"
            })

            pending = await db.pending_registrations.find_one({"email": test_email})
            v_id = pending["verification_id"]
            real_otp = None
            for cand in range(0, 1_000_000):
                cand_str = f"{cand:06d}"
                if verify_registration_otp_hash(test_email, cand_str, v_id, pending["otp_hash"]):
                    real_otp = cand_str
                    break
            assert real_otp is not None

            # First verification succeeds
            v1 = await ac.post("/api/v1/auth/verify-email", json={
                "email": test_email,
                "code": real_otp,
                "verification_id": v_id
            })
            assert v1.status_code == 200

            # Second verification with same code: pending record is already gone
            # Since user is now verified, verify-email acknowledges already verified or fails safely
            v2 = await ac.post("/api/v1/auth/verify-email", json={
                "email": test_email,
                "code": real_otp,
                "verification_id": v_id
            })
            # It must not allow creating another user or processing pending_registrations again
            assert v2.status_code in [200, 400]
            if v2.status_code == 200:
                assert "already verified" in v2.json()["message"].lower()

            # Exactly one user in users collection
            assert await db.users.count_documents({"email": test_email}) == 1


@pytest.mark.asyncio
async def test_five_failed_attempts_deletes_pending_record():
    """Validates that 5 failed attempts delete the pending record and require re-registration."""
    test_email = "karuppusamyc60@gmail.com"
    db = get_database()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.email_service.EmailService.send_verification_otp", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            await ac.post("/api/v1/auth/register", json={
                "email": test_email,
                "username": "zenova_five_attempts",
                "full_name": "Five Attempts User",
                "password": "Password123!"
            })

            # Submit 5 wrong OTPs
            for _ in range(5):
                res = await ac.post("/api/v1/auth/verify-email", json={
                    "email": test_email,
                    "code": "000000"
                })
                assert res.status_code == 400
                assert res.json()["detail"] == "Invalid or expired OTP"

            # Pending record must be deleted
            assert await db.pending_registrations.find_one({"email": test_email}) is None
            assert await db.users.find_one({"email": test_email}) is None


@pytest.mark.asyncio
async def test_resend_cooldown_and_anti_enumeration():
    """Validates 60s cooldown per email, generic response (no enumeration), and replacement of old hash."""
    test_email = "karuppusamyc80@gmail.com"
    db = get_database()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.email_service.EmailService.send_verification_otp", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            # Register
            await ac.post("/api/v1/auth/register", json={
                "email": test_email,
                "username": "zenova_resend_user",
                "full_name": "Resend User",
                "password": "Password123!"
            })
            pending1 = await db.pending_registrations.find_one({"email": test_email})
            old_hash = pending1["otp_hash"]

            # Immediate resend should hit 60s cooldown (429)
            resend_429 = await ac.post("/api/v1/auth/resend-otp", json={"email": test_email})
            assert resend_429.status_code == 429
            assert "please wait" in resend_429.json()["detail"].lower()

            # Age the cooldown timestamp in pending_registrations
            await db.pending_registrations.update_one(
                {"email": test_email},
                {"$set": {"resend_eligible_at": datetime.now(timezone.utc) - timedelta(seconds=2)}}
            )

            # Resend now succeeds with generic response
            resend_ok = await ac.post("/api/v1/auth/resend-otp", json={"email": test_email})
            assert resend_ok.status_code == 200
            assert "a new verification code has been sent" in resend_ok.json()["message"].lower()

            # Verify that hash was replaced and attempts reset
            pending2 = await db.pending_registrations.find_one({"email": test_email})
            assert pending2["otp_hash"] != old_hash
            assert pending2["attempts"] == 0

            # Test anti-enumeration: resend for non-existent email returns same response
            resend_nonexistent = await ac.post("/api/v1/auth/resend-otp", json={"email": "nonexistent@gmail.com"})
            assert resend_nonexistent.status_code == 200
            assert resend_nonexistent.json()["message"] == resend_ok.json()["message"]


@pytest.mark.asyncio
async def test_email_send_failure_rollback():
    """Validates that if email sending fails, the pending record is deleted and generic 500 is returned."""
    test_email = "fortemp300@gmail.com"
    db = get_database()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.email_service.EmailService.send_verification_otp", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = False  # Failure

            resp = await ac.post("/api/v1/auth/register", json={
                "email": test_email,
                "username": "zenova_fail_user",
                "full_name": "Fail User",
                "password": "Password123!"
            })
            assert resp.status_code == 500
            assert "failed to send verification email" in resp.json()["detail"].lower()

            # Pending record must be deleted
            assert await db.pending_registrations.find_one({"email": test_email}) is None
            assert await db.users.find_one({"email": test_email}) is None


@pytest.mark.asyncio
async def test_atomic_failed_attempt_increment_and_threshold():
    """
    Validates atomic increment with find_one_and_update ($inc and return_document=AFTER)
    and that attempts >= 5 triggers deletion of the pending record.
    """
    test_email = "karuppusamyc60@gmail.com"
    db = get_database()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.email_service.EmailService.send_verification_otp", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            await ac.post("/api/v1/auth/register", json={
                "email": test_email,
                "username": "zenova_atomic_inc",
                "full_name": "Atomic Inc User",
                "password": "Password123!"
            })

            pending = await db.pending_registrations.find_one({"email": test_email})
            assert pending is not None
            assert pending["attempts"] == 0

            # 4 consecutive failed attempts
            for expected_attempts in range(1, 5):
                res = await ac.post("/api/v1/auth/verify-email", json={
                    "email": test_email,
                    "code": "000000"
                })
                assert res.status_code == 400
                assert res.json()["detail"] == "Invalid or expired OTP"
                doc = await db.pending_registrations.find_one({"email": test_email})
                assert doc is not None
                assert doc["attempts"] == expected_attempts

            # 5th failed attempt: atomic $inc reaches 5 -> deleted
            res5 = await ac.post("/api/v1/auth/verify-email", json={
                "email": test_email,
                "code": "000000"
            })
            assert res5.status_code == 400
            assert res5.json()["detail"] == "Invalid or expired OTP"

            # Pending record must be deleted
            assert await db.pending_registrations.find_one({"email": test_email}) is None


@pytest.mark.asyncio
async def test_register_per_email_rate_limit():
    """Validates that register has per-email rate limiting in addition to per-IP."""
    test_email = "karuppusamyc80@gmail.com"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.email_service.EmailService.send_verification_otp", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            # Exhaust rate limiter for this email (limit is 10)
            for i in range(10):
                resp = await ac.post("/api/v1/auth/register", json={
                    "email": test_email,
                    "username": f"user_rate_{i}",
                    "full_name": "Rate User",
                    "password": "Password123!"
                })
                assert resp.status_code in [201, 400]

            # 11th request for same email hits rate limit (429)
            resp_429 = await ac.post("/api/v1/auth/register", json={
                "email": test_email,
                "username": "user_rate_blocked",
                "full_name": "Rate User",
                "password": "Password123!"
            })
            assert resp_429.status_code == 429


@pytest.mark.asyncio
async def test_register_duplicate_key_error_handling():
    """Validates that DuplicateKeyError on pending_registrations returns 400 generic error instead of 500."""
    from pymongo.errors import DuplicateKeyError
    from motor.motor_asyncio import AsyncIOMotorCollection
    test_email = "fortemp300@gmail.com"

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch.object(AsyncIOMotorCollection, "update_one", side_effect=DuplicateKeyError("E11000 duplicate key error")):
            resp = await ac.post("/api/v1/auth/register", json={
                "email": test_email,
                "username": "dup_key_user",
                "full_name": "Dup Key User",
                "password": "Password123!"
            })
            assert resp.status_code == 400
            assert "already exists" in resp.json()["detail"].lower()
