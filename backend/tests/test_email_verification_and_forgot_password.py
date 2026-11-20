import pytest
import uuid
import asyncio
from datetime import datetime, timezone
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database.client import connect_to_database, close_database_connection, get_database
from app.core.rate_limit import auth_rate_limiter
from app.core.otp_service import OTPService, _delete_store, EMAIL_VERIFY_PREFIX, EMAIL_VERIFY_CD_PREFIX, PWD_RESET_PREFIX, PWD_RESET_CD_PREFIX

@pytest.fixture(autouse=True)
async def isolated_auth_test_env():
    """Sets up database connection and cleans up test users."""
    await connect_to_database()
    auth_rate_limiter.requests.clear()
    
    created_test_emails = []
    
    def register_test_email(email: str):
        created_test_emails.append(email)
        
    yield register_test_email
    
    db = get_database()
    if db is not None and created_test_emails:
        users_to_delete = await db.users.find({"email": {"$in": created_test_emails}}).to_list(length=100)
        user_ids = [str(u["_id"]) for u in users_to_delete]
        
        await db.users.delete_many({"email": {"$in": created_test_emails}})
        await db.refresh_tokens.delete_many({"user_id": {"$in": user_ids}})
        await db.user_preferences.delete_many({"user_id": {"$in": user_ids}})

    for em in created_test_emails:
        await _delete_store(f"{EMAIL_VERIFY_PREFIX}{em.lower().strip()}")
        await _delete_store(f"{EMAIL_VERIFY_CD_PREFIX}{em.lower().strip()}")
        await _delete_store(f"{PWD_RESET_PREFIX}{em.lower().strip()}")
        await _delete_store(f"{PWD_RESET_CD_PREFIX}{em.lower().strip()}")
        
    await close_database_connection()


@pytest.mark.asyncio
async def test_full_email_verification_lifecycle(isolated_auth_test_env):
    """
    Validates complete email verification flow:
    1. Register -> creates unverified account
    2. Login before verification -> rejected with 403 Forbidden (EMAIL_NOT_VERIFIED)
    3. Wrong OTP -> rejected
    4. Valid OTP -> verified
    5. Login after verification -> succeeds
    """
    unique = str(uuid.uuid4())[:8]
    test_email = f"verify_{unique}@intellidev.in"
    password = "SecurePassword123!"
    isolated_auth_test_env(test_email)

    with patch("app.services.email_service.EmailService.send_email", new_callable=AsyncMock) as mock_send, \
         patch("app.core.otp_service.generate_six_digit_code", return_value="654321"):
        mock_send.return_value = True

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # 1. Register
            reg_res = await ac.post("/api/v1/auth/register", json={
                "email": test_email,
                "username": f"usr_{unique}",
                "full_name": "Test User",
                "password": password
            })
            assert reg_res.status_code == 201
            reg_data = reg_res.json()
            assert reg_data["status"] == "verification_required"
            assert reg_data["email"] == test_email
            assert mock_send.called

            # Check DB is_verified is False
            db = get_database()
            user_in_db = await db.users.find_one({"email": test_email})
            assert user_in_db is not None
            assert user_in_db.get("is_verified") is False

            # 2. Login before verification must fail with 403
            login_fail = await ac.post("/api/v1/auth/login", json={
                "email": test_email,
                "password": password
            })
            assert login_fail.status_code == 403
            assert "not verified" in login_fail.json()["detail"].lower()

            # 3. Verify with incorrect code
            wrong_res = await ac.post("/api/v1/auth/verify-email", json={
                "email": test_email,
                "code": "000000"
            })
            assert wrong_res.status_code == 400
            assert "invalid" in wrong_res.json()["detail"].lower()

            # 4. Verify with correct code ("654321")
            verify_res = await ac.post("/api/v1/auth/verify-email", json={
                "email": test_email,
                "code": "654321"
            })
            assert verify_res.status_code == 200
            assert verify_res.json()["status"] == "verified"

            # Check DB is_verified is True
            user_verified = await db.users.find_one({"email": test_email})
            assert user_verified.get("is_verified") is True
            assert user_verified.get("verified_at") is not None

            # 5. Login now succeeds
            login_success = await ac.post("/api/v1/auth/login", json={
                "email": test_email,
                "password": password
            })
            assert login_success.status_code == 200
            tokens = login_success.json()
            assert "access_token" in tokens
            assert tokens["user"]["is_verified"] is True


@pytest.mark.asyncio
async def test_resend_verification_cooldown(isolated_auth_test_env):
    """Verifies that resending verification codes enforces a 60-second cooldown."""
    unique = str(uuid.uuid4())[:8]
    test_email = f"cooldown_{unique}@intellidev.in"
    password = "SecurePassword123!"
    isolated_auth_test_env(test_email)

    with patch("app.services.email_service.EmailService.send_email", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            await ac.post("/api/v1/auth/register", json={
                "email": test_email,
                "username": f"cd_{unique}",
                "full_name": "Cooldown User",
                "password": password
            })

            # Immediate resend attempt should hit 429 Too Many Requests
            resend_res = await ac.post("/api/v1/auth/resend-verification-code", json={
                "email": test_email
            })
            assert resend_res.status_code == 429
            assert "wait" in resend_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_forgot_password_and_reset_workflow(isolated_auth_test_env):
    """
    Validates complete Forgot Password flow:
    1. Request reset code -> email dispatched
    2. Verify code -> receives reset_token
    3. Reset password with reset_token -> updates DB, invalidates old sessions
    4. Old password rejected, new password accepted
    5. Replay of reset_token rejected
    """
    unique = str(uuid.uuid4())[:8]
    test_email = f"reset_{unique}@intellidev.in"
    old_password = "OldPassword123!"
    new_password = "NewStrongPassword456!"
    isolated_auth_test_env(test_email)

    db = get_database()
    from app.core.security import get_password_hash
    # Create an active verified user
    await db.users.insert_one({
        "email": test_email,
        "username": f"reset_{unique}",
        "full_name": "Reset User",
        "hashed_password": get_password_hash(old_password),
        "is_active": True,
        "is_verified": True,
        "created_at": datetime.now(timezone.utc)
    })

    with patch("app.services.email_service.EmailService.send_email", new_callable=AsyncMock) as mock_send, \
         patch("app.core.otp_service.generate_six_digit_code", return_value="789012"):
        mock_send.return_value = True

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # 1. Forgot password request
            forgot_res = await ac.post("/api/v1/auth/forgot-password", json={
                "email": test_email
            })
            assert forgot_res.status_code == 200
            assert forgot_res.json()["status"] == "success"
            assert mock_send.called

            # 2. Verify with wrong code
            bad_code_res = await ac.post("/api/v1/auth/verify-reset-code", json={
                "email": test_email,
                "code": "111111"
            })
            assert bad_code_res.status_code == 400

            # Verify with correct code ("789012")
            verify_res = await ac.post("/api/v1/auth/verify-reset-code", json={
                "email": test_email,
                "code": "789012"
            })
            assert verify_res.status_code == 200
            reset_token = verify_res.json()["reset_token"]
            assert reset_token is not None

            # 3. Reset password (mismatch confirm)
            mismatch_res = await ac.post("/api/v1/auth/reset-password", json={
                "email": test_email,
                "reset_token": reset_token,
                "new_password": new_password,
                "confirm_password": "DifferentPassword!"
            })
            assert mismatch_res.status_code == 400

            # Reset password (success)
            reset_res = await ac.post("/api/v1/auth/reset-password", json={
                "email": test_email,
                "reset_token": reset_token,
                "new_password": new_password,
                "confirm_password": new_password
            })
            assert reset_res.status_code == 200
            assert reset_res.json()["status"] == "success"

            # 4. Token replay attempt must fail
            replay_res = await ac.post("/api/v1/auth/reset-password", json={
                "email": test_email,
                "reset_token": reset_token,
                "new_password": "AnotherPassword999!",
                "confirm_password": "AnotherPassword999!"
            })
            assert replay_res.status_code == 400

            # 5. Old password rejected at login
            old_login = await ac.post("/api/v1/auth/login", json={
                "email": test_email,
                "password": old_password
            })
            assert old_login.status_code == 401

            # 6. Login with new password succeeds
            new_login = await ac.post("/api/v1/auth/login", json={
                "email": test_email,
                "password": new_password
            })
            assert new_login.status_code == 200
            assert "access_token" in new_login.json()
