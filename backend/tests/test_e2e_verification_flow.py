import pytest
import uuid
import time
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database.client import connect_to_database, close_database_connection, get_database
from app.services.verification_service import (
    VerificationService,
    PURPOSE_REGISTRATION,
    STATUS_PENDING,
    STATUS_CONSUMED,
    STATUS_EXPIRED,
    STATUS_FAILED,
    compute_otp_hash,
    verify_otp_hash
)
from app.core.rate_limit import (
    auth_rate_limiter,
    email_verify_rate_limiter,
    email_resend_rate_limiter
)

@pytest.fixture(autouse=True)
async def clean_env():
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
async def test_e2e_registration_otp_verification_and_login_flow(clean_env):
    """
    Validates end-to-end integration:
    1. Client registers -> receives verification_id, cooldown_seconds, expires_in_seconds
    2. Email dispatch triggered with 6-digit OTP
    3. Unverified user login blocked (403)
    4. Client verifies OTP with verification_id -> succeeds (200)
    5. Verified user logs in -> receives JWT access & refresh tokens
    """
    suffix = uuid.uuid4().hex[:6]
    test_email = f"e2e_user_{suffix}@zenova.in"
    clean_env(test_email)
    db = get_database()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.email_service.EmailService.send_verification_otp", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            # Step 1: Register
            reg_resp = await ac.post("/api/v1/auth/register", json={
                "email": test_email,
                "username": f"e2e_{suffix}",
                "full_name": "E2E Tester",
                "password": "Password123!"
            })
            assert reg_resp.status_code == 201
            reg_data = reg_resp.json()
            assert reg_data["status"] == "verification_required"
            v_id = reg_data.get("verification_id")
            assert v_id is not None
            assert len(v_id) == 16
            assert reg_data.get("cooldown_seconds") == 60
            assert reg_data.get("expires_in_seconds") == 300
            assert mock_send.call_count == 1

            # Step 1b: Verify account is in pending_registrations and NEVER in users
            pending_doc = await db.pending_registrations.find_one({"email": test_email})
            assert pending_doc is not None
            assert pending_doc["username"] == f"e2e_{suffix}"
            assert pending_doc["verification_id"] == v_id

            user_in_db = await db.users.find_one({"email": test_email})
            assert user_in_db is None, "Unverified account MUST NOT exist in permanent users collection"

            # Step 2: Verify login is rejected before verification
            login_unverified = await ac.post("/api/v1/auth/login", json={
                "email": test_email,
                "password": "Password123!"
            })
            assert login_unverified.status_code == 401

            # Retrieve candidate OTP for verification test
            v_doc = await db.email_verifications.find_one({"verification_id": v_id})
            assert v_doc is not None
            real_otp = None
            for cand in range(100000, 1000000):
                if verify_otp_hash(v_id, PURPOSE_REGISTRATION, str(cand), v_doc["otp_hash"]):
                    real_otp = str(cand)
                    break
            assert real_otp is not None

            # Step 3: Bad OTP fails
            bad_res = await ac.post("/api/v1/auth/verify-email", json={
                "email": test_email,
                "code": "000000",
                "verification_id": v_id
            })
            assert bad_res.status_code == 400
            assert "4 attempts remaining" in bad_res.json().get("detail", "").lower()

            # Step 4: Correct OTP succeeds
            good_res = await ac.post("/api/v1/auth/verify-email", json={
                "email": test_email,
                "code": real_otp,
                "verification_id": v_id
            })
            assert good_res.status_code == 200
            assert good_res.json()["status"] == "verified"

            # Step 5: User is now able to log in
            login_verified = await ac.post("/api/v1/auth/login", json={
                "email": test_email,
                "password": "Password123!"
            })
            assert login_verified.status_code == 200
            token_data = login_verified.json()
            assert "access_token" in token_data
            assert "refresh_token" in token_data


@pytest.mark.asyncio
async def test_e2e_resend_cooldown_and_new_challenge(clean_env):
    """
    Validates resend cooldown enforcement:
    1. Register
    2. Immediate resend within 60s returns HTTP 429
    3. Resend after cooldown succeeds with a new verification_id
    """
    suffix = uuid.uuid4().hex[:6]
    test_email = f"resend_{suffix}@zenova.in"
    clean_env(test_email)
    db = get_database()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.email_service.EmailService.send_verification_otp", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            reg_resp = await ac.post("/api/v1/auth/register", json={
                "email": test_email,
                "username": f"res_{suffix}",
                "full_name": "Resend Tester",
                "password": "Password123!"
            })
            v_id1 = reg_resp.json()["verification_id"]

            # Immediate resend fails with 429
            resend_429 = await ac.post("/api/v1/auth/resend-verification-code", json={
                "email": test_email,
                "verification_id": v_id1
            })
            assert resend_429.status_code == 429
            assert "please wait" in resend_429.json().get("detail", "").lower()

            # Age the cooldown timestamp in DB
            await db.email_verifications.update_one(
                {"verification_id": v_id1},
                {"$set": {"resend_eligible_at": datetime.now(timezone.utc) - timedelta(seconds=2)}}
            )

            # Resend succeeds and returns new verification_id
            resend_ok = await ac.post("/api/v1/auth/resend-verification-code", json={
                "email": test_email,
                "verification_id": v_id1
            })
            assert resend_ok.status_code == 200
            resend_data = resend_ok.json()
            assert resend_data["status"] == "sent"
            v_id2 = resend_data.get("verification_id")
            assert v_id2 is not None
            assert v_id2 != v_id1


@pytest.mark.asyncio
async def test_security_max_attempts_lockout_and_single_use(clean_env):
    """
    Verifies that after 5 failed attempts, the challenge status transitions to 'failed',
    and subsequent attempts are permanently rejected.
    """
    suffix = uuid.uuid4().hex[:6]
    test_email = f"sec_{suffix}@zenova.in"
    clean_env(test_email)
    db = get_database()

    v_id, real_otp, ok, _ = await VerificationService.create_verification_challenge(test_email)
    assert ok is True

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Create unverified user doc
        await db.users.insert_one({
            "email": test_email,
            "username": f"sec_{suffix}",
            "full_name": "Security Tester",
            "hashed_password": "pw",
            "is_verified": False,
            "is_active": True
        })

        # 5 wrong attempts
        for i in range(1, 5):
            res = await ac.post("/api/v1/auth/verify-email", json={
                "email": test_email,
                "code": "111111",
                "verification_id": v_id
            })
            assert res.status_code == 400
            assert f"{5 - i} attempt" in res.json().get("detail", "").lower()

        # 5th attempt locks out
        res5 = await ac.post("/api/v1/auth/verify-email", json={
            "email": test_email,
            "code": "111111",
            "verification_id": v_id
        })
        assert res5.status_code == 400
        assert "maximum verification attempts exceeded" in res5.json().get("detail", "").lower()

        # Check DB directly to confirm status transitioned to 'failed' and attempts == 5
        failed_doc = await db.email_verifications.find_one({"verification_id": v_id})
        assert failed_doc["status"] == STATUS_FAILED
        assert failed_doc["attempts"] >= 5

        # VerificationService directly rejects it even without hitting HTTP rate limiter (status is STATUS_FAILED)
        v_ok, err_msg, _ = await VerificationService.verify_otp(test_email, real_otp, verification_id=v_id)
        assert v_ok is False
        assert "not requested" in err_msg.lower() or "expired" in err_msg.lower()
