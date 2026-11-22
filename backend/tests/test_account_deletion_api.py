import pytest
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone
from bson import ObjectId

from app.main import app
from app.database.client import connect_to_database, close_database_connection, get_database
from app.core.security import get_password_hash, create_access_token
from app.core.otp_service import OTPService

@pytest.fixture(autouse=True)
async def setup_api_fixture():
    await connect_to_database()
    yield
    await close_database_connection()

@pytest.mark.asyncio
async def test_account_deletion_and_recovery_endpoints():
    db = get_database()
    if db is None:
        pytest.skip("MongoDB required for API test")

    email = "api_deletion_test@intellidev.in"
    password = "ComplexPassword890!"
    user_doc = {
        "email": email,
        "username": "api_del_user",
        "full_name": "API Deletion User",
        "hashed_password": get_password_hash(password),
        "is_active": True,
        "is_verified": True,
        "account_status": "active",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    await db.users.delete_many({"email": email})
    ins = await db.users.insert_one(user_doc)
    user_id = str(ins.inserted_id)

    try:
        token = create_access_token({"sub": user_id, "email": email})
        headers = {"Authorization": f"Bearer {token}"}

        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # 1. Check initial deletion status -> active
            stat_res = await ac.get("/api/v1/account/deletion/status", headers=headers)
            assert stat_res.status_code == 200
            assert stat_res.json()["account_status"] == "active"

            # 2. Reject deletion with bad password
            bad_req = await ac.post("/api/v1/account/deletion/request", headers=headers, json={"password": "WrongPassword"})
            assert bad_req.status_code == 400

            # 3. Successful Day 0 deletion request
            del_req = await ac.post("/api/v1/account/deletion/request", headers=headers, json={"password": password, "reason": "Testing API"})
            assert del_req.status_code == 200
            data = del_req.json()
            assert data["status"] == "pending_deletion"
            assert data["days_remaining"] == 30

            # 4. Immediate block: normal authenticated request with old or new token is blocked
            blocked_me = await ac.get("/api/v1/auth/me", headers=headers)
            assert blocked_me.status_code == 403
            assert blocked_me.headers.get("x-error-code") == "ACCOUNT_PENDING_DELETION"

            # 5. Immediate block: normal login is blocked with 403
            blocked_login = await ac.post("/api/v1/auth/login", json={"email": email, "password": password})
            assert blocked_login.status_code == 403
            assert blocked_login.headers.get("x-error-code") == "ACCOUNT_PENDING_DELETION"

            # 6. Request Recovery OTP
            await OTPService.clear_cooldown(email)
            otp_req = await ac.post("/api/v1/account/deletion/recovery-otp", json={"email": email})
            assert otp_req.status_code == 200

            # 7. Test Recovery with invalid OTP
            bad_rec = await ac.post("/api/v1/account/deletion/recover", json={
                "email": email,
                "password": password,
                "otp_code": "000000"
            })
            assert bad_rec.status_code == 400

            # 8. Test Recovery with valid OTP
            await OTPService.clear_cooldown(email)
            valid_otp, ok, _ = await OTPService.create_email_verification_otp(email)
            assert ok is True

            good_rec = await ac.post("/api/v1/account/deletion/recover", json={
                "email": email,
                "password": password,
                "otp_code": valid_otp
            })
            assert good_rec.status_code == 200
            rec_data = good_rec.json()
            assert rec_data["status"] == "recovered"
            assert rec_data["account_status"] == "active"

            # 9. Normal login works again after recovery
            login_again = await ac.post("/api/v1/auth/login", json={"email": email, "password": password})
            assert login_again.status_code == 200
            assert "access_token" in login_again.json()

    finally:
        await db.users.delete_many({"email": email})
        await db.deletion_jobs.delete_many({"user_id": user_id})
