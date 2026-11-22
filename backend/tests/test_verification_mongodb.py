import pytest
import uuid
import time
import asyncio
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database.client import connect_to_database, close_database_connection, get_database
from app.core.config import settings
from app.services.verification_service import (
    VerificationService,
    generate_verification_id,
    generate_six_digit_otp,
    compute_otp_hash,
    verify_otp_hash,
    PURPOSE_REGISTRATION,
    STATUS_PENDING,
    STATUS_CONSUMED,
    STATUS_EXPIRED,
    STATUS_FAILED
)
from app.core.rate_limit import (
    auth_rate_limiter,
    email_verify_rate_limiter,
    email_resend_rate_limiter
)
from app.core.otp_service import OTPService

@pytest.fixture(autouse=True)
async def clean_test_env():
    await connect_to_database()
    auth_rate_limiter.requests.clear()
    email_verify_rate_limiter.requests.clear()
    email_resend_rate_limiter.requests.clear()
    
    test_emails = []
    
    def register_email(email: str):
        test_emails.append(email.lower().strip())
        
    yield register_email
    
    db = get_database()
    if db is not None and test_emails:
        await db.users.delete_many({"email": {"$in": test_emails}})
        await db.email_verifications.delete_many({"email": {"$in": test_emails}})
    
    await close_database_connection()


def test_verification_id_generation():
    v1 = generate_verification_id()
    v2 = generate_verification_id()
    assert len(v1) == 16
    assert len(v2) == 16
    assert v1.isupper() or v1.isalnum()
    assert v1 != v2


def test_otp_generation():
    otp1 = generate_six_digit_otp()
    otp2 = generate_six_digit_otp()
    assert len(otp1) == 6
    assert len(otp2) == 6
    assert otp1.isdigit()
    assert otp2.isdigit()


def test_hmac_hash_correctness_and_binding():
    v_id = "ABCD1234EFGH5678"
    otp = "654321"
    purpose = PURPOSE_REGISTRATION

    h1 = compute_otp_hash(v_id, purpose, otp)
    assert verify_otp_hash(v_id, purpose, otp, h1) is True

    # Tampered OTP fails
    assert verify_otp_hash(v_id, purpose, "654322", h1) is False
    # Tampered verification_id fails
    assert verify_otp_hash("WXYZ1234EFGH5678", purpose, otp, h1) is False
    # Tampered purpose fails
    assert verify_otp_hash(v_id, "password_reset", otp, h1) is False


@pytest.mark.asyncio
async def test_challenge_creation_and_resend_cooldown(clean_test_env):
    email = f"cooldown_test_{uuid.uuid4().hex[:6]}@zenova.in"
    clean_test_env(email)

    v_id1, otp1, ok1, cd1 = await VerificationService.create_verification_challenge(email)
    assert ok1 is True
    assert len(v_id1) == 16
    assert len(otp1) == 6
    assert cd1 == 0

    # Immediate second request triggers cooldown
    v_id2, otp2, ok2, cd2 = await VerificationService.create_verification_challenge(email)
    assert ok2 is False
    assert otp2 is None
    assert cd2 > 0
    assert cd2 <= 60


@pytest.mark.asyncio
async def test_single_active_challenge_superseding(clean_test_env):
    email = f"supersede_{uuid.uuid4().hex[:6]}@zenova.in"
    clean_test_env(email)
    db = get_database()

    v_id1, otp1, ok1, _ = await VerificationService.create_verification_challenge(email)
    assert ok1 is True

    # Artificially age resend_eligible_at to bypass cooldown
    await db.email_verifications.update_one(
        {"verification_id": v_id1},
        {"$set": {"resend_eligible_at": datetime.now(timezone.utc) - timedelta(seconds=5)}}
    )

    # Second creation succeeds and supersedes the first
    v_id2, otp2, ok2, _ = await VerificationService.create_verification_challenge(email)
    assert ok2 is True
    assert v_id2 != v_id1

    # Check status of v_id1 in DB -> must be expired
    old_doc = await db.email_verifications.find_one({"verification_id": v_id1})
    assert old_doc["status"] == STATUS_EXPIRED

    # New doc is pending
    new_doc = await db.email_verifications.find_one({"verification_id": v_id2})
    assert new_doc["status"] == STATUS_PENDING


@pytest.mark.asyncio
async def test_verification_success_and_single_use(clean_test_env):
    email = f"success_{uuid.uuid4().hex[:6]}@zenova.in"
    clean_test_env(email)

    v_id, otp, ok, _ = await VerificationService.create_verification_challenge(email)
    assert ok is True

    # 1. Successful verification
    v_ok, err, returned_id = await VerificationService.verify_otp(email, otp, verification_id=v_id)
    assert v_ok is True
    assert err == ""
    assert returned_id == v_id

    # 2. Second use fails (single use enforcement)
    v_ok2, err2, _ = await VerificationService.verify_otp(email, otp, verification_id=v_id)
    assert v_ok2 is False
    assert "expired or was not requested" in err2.lower()


@pytest.mark.asyncio
async def test_invalid_otp_and_attempt_lockout(clean_test_env):
    email = f"lockout_{uuid.uuid4().hex[:6]}@zenova.in"
    clean_test_env(email)

    v_id, real_otp, ok, _ = await VerificationService.create_verification_challenge(email)
    assert ok is True

    # Attempt 1 to 4 with bad OTP
    for i in range(1, 5):
        v_ok, err, _ = await VerificationService.verify_otp(email, "000000", verification_id=v_id)
        assert v_ok is False
        assert f"{5 - i} attempt" in err

    # Attempt 5 -> lock out
    v_ok5, err5, _ = await VerificationService.verify_otp(email, "000000", verification_id=v_id)
    assert v_ok5 is False
    assert "maximum verification attempts exceeded" in err5.lower()

    # Even providing real OTP now fails
    v_ok_real, err_real, _ = await VerificationService.verify_otp(email, real_otp, verification_id=v_id)
    assert v_ok_real is False


@pytest.mark.asyncio
async def test_expired_otp_rejection(clean_test_env):
    email = f"expired_{uuid.uuid4().hex[:6]}@zenova.in"
    clean_test_env(email)
    db = get_database()

    v_id, otp, ok, _ = await VerificationService.create_verification_challenge(email)
    assert ok is True

    # Simulate expiration by setting expires_at to the past
    await db.email_verifications.update_one(
        {"verification_id": v_id},
        {"$set": {"expires_at": datetime.now(timezone.utc) - timedelta(minutes=1)}}
    )

    v_ok, err, _ = await VerificationService.verify_otp(email, otp, verification_id=v_id)
    assert v_ok is False
    assert "expired" in err.lower()


@pytest.mark.asyncio
async def test_concurrent_verification_attempts_single_winner(clean_test_env):
    email = f"race_{uuid.uuid4().hex[:6]}@zenova.in"
    clean_test_env(email)

    v_id, otp, ok, _ = await VerificationService.create_verification_challenge(email)
    assert ok is True

    # Dispatch 5 simultaneous verification attempts with the correct OTP
    tasks = [
        VerificationService.verify_otp(email, otp, verification_id=v_id)
        for _ in range(5)
    ]
    results = await asyncio.gather(*tasks)

    # Exactly one request must succeed (single-use consumption race protection)
    successes = [r for r in results if r[0] is True]
    assert len(successes) == 1


@pytest.mark.asyncio
async def test_api_auth_registration_and_email_verification_flow(clean_test_env):
    email = f"api_test_{uuid.uuid4().hex[:6]}@zenova.in"
    clean_test_env(email)
    db = get_database()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        with patch("app.services.email_service.EmailService.send_verification_otp", new_callable=AsyncMock) as mock_send:
            mock_send.return_value = True

            # 1. Register new user
            reg_resp = await ac.post("/api/v1/auth/register", json={
                "email": email,
                "username": f"user_{uuid.uuid4().hex[:6]}",
                "full_name": "Zenova User",
                "password": "Password123!"
            })
            assert reg_resp.status_code == 201
            reg_data = reg_resp.json()
            assert reg_data["status"] == "verification_required"
            v_id = reg_data.get("verification_id")
            assert v_id is not None
            assert len(v_id) == 16
            assert mock_send.call_count == 1

            # Fetch OTP from db hash for testing
            verif_doc = await db.email_verifications.find_one({"verification_id": v_id})
            assert verif_doc is not None

            # Retrieve generated OTP via matching verification
            test_otp = None
            for candidate in range(100000, 1000000):
                if verify_otp_hash(v_id, PURPOSE_REGISTRATION, str(candidate), verif_doc["otp_hash"]):
                    test_otp = str(candidate)
                    break
            assert test_otp is not None

            # 2. Verify with wrong OTP -> 400
            bad_verify = await ac.post("/api/v1/auth/verify-email", json={
                "email": email,
                "code": "000000",
                "verification_id": v_id
            })
            assert bad_verify.status_code == 400

            # 3. Verify with valid OTP -> 200
            good_verify = await ac.post("/api/v1/auth/verify-email", json={
                "email": email,
                "code": test_otp,
                "verification_id": v_id
            })
            assert good_verify.status_code == 200
            assert good_verify.json()["status"] == "verified"

            # 4. Check user in MongoDB is marked is_verified: True
            user_doc = await db.users.find_one({"email": email})
            assert user_doc["is_verified"] is True


@pytest.mark.asyncio
async def test_pending_legacy_registration_compatibility(clean_test_env):
    """
    Verifies that a user whose OTP was created before Phase 3 (in Redis / memory store only)
    can still successfully verify their email address without error.
    """
    email = f"legacy_compat_{uuid.uuid4().hex[:6]}@zenova.in"
    clean_test_env(email)
    db = get_database()

    # Create unverified user in DB
    await db.users.insert_one({
        "email": email,
        "username": f"leg_{uuid.uuid4().hex[:6]}",
        "full_name": "Legacy User",
        "hashed_password": "mock_hashed_pw",
        "is_active": True,
        "is_verified": False,
        "created_at": datetime.now(timezone.utc)
    })

    # Store OTP in legacy OTPService only (simulate pre-migration in-flight challenge)
    code, ok, _ = await OTPService.create_email_verification_otp(email)
    assert ok is True

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Legacy client request without verification_id
        res = await ac.post("/api/v1/auth/verify-email", json={
            "email": email,
            "code": code
        })
        assert res.status_code == 200
        assert res.json()["status"] == "verified"

        user = await db.users.find_one({"email": email})
        assert user["is_verified"] is True
