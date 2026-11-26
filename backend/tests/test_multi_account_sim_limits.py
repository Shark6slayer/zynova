import pytest
import pytest_asyncio
from unittest.mock import patch, AsyncMock
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone
from bson import ObjectId
from app.main import app
from app.database.client import connect_to_database, get_database
from app.core.rate_limit import auth_rate_limiter, phone_verify_rate_limiter

TEST_EMAILS = [
    "multi_personal_test@zenova.id",
    "multi_prof_test@zenova.id",
    "multi_overflow_test@zenova.id"
]

@pytest.fixture(autouse=True)
async def setup_test_db():
    await connect_to_database()
    auth_rate_limiter.requests.clear()
    phone_verify_rate_limiter.requests.clear()
    db = get_database()
    if db is not None:
        await db.users.delete_many({"email": {"$in": TEST_EMAILS}})
        await db.pending_registrations.delete_many({"email": {"$in": TEST_EMAILS}})
        await db.users.delete_many({"phone_number": "+919999911111"})
    yield
    if db is not None:
        await db.users.delete_many({"email": {"$in": TEST_EMAILS}})
        await db.pending_registrations.delete_many({"email": {"$in": TEST_EMAILS}})
        await db.users.delete_many({"phone_number": "+919999911111"})

@pytest.mark.asyncio
async def test_multi_account_phone_eligibility_and_limits():
    """
    Validates ZENOVA Phase 1 & Phase 7 Multi-Account SIM-Bound limits:
    - 1 phone number can hold at most 2 accounts: 1 Personal, 1 Professional.
    - 1 phone number cannot hold 2 Personal or 2 Professional accounts.
    - 1 email cannot be reused across accounts.
    - /phone-eligibility returns accurate capacity.
    """
    transport = ASGITransport(app=app)
    with patch("app.services.email_service.EmailService.send_verification_otp", new_callable=AsyncMock, return_value=True):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            test_phone = "+919999911111"

            # 1. Initially, eligibility for test_phone should allow both personal and professional
            resp = await client.get(f"/api/v1/auth/phone-eligibility?phone_number={test_phone}")
            assert resp.status_code == 200, resp.text
            data = resp.json()
            assert data["eligible"] is True
            assert data["max_reached"] is False
            assert "personal" in data["available_types"]
            assert "professional" in data["available_types"]
            assert data["account_count"] == 0

            db = get_database()
            now = datetime.now(timezone.utc)

            # 2. Insert verified Personal account
            user1_id = ObjectId()
            await db.users.insert_one({
                "_id": user1_id,
                "email": "multi_personal_test@zenova.id",
                "username": "multi_personal_user",
                "full_name": "Multi Personal User",
                "account_type": "personal",
                "phone_number": test_phone,
                "is_phone_verified": True,
                "zen_id": "zen_multi_personal",
                "is_active": True,
                "is_verified": True,
                "created_at": now
            })

            # 3. Check eligibility after 1 Personal account: only professional should remain
            resp = await client.get(f"/api/v1/auth/phone-eligibility?phone_number={test_phone}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["eligible"] is True
            assert data["max_reached"] is False
            assert data["existing_types"] == ["personal"]
            assert data["available_types"] == ["professional"]
            assert data["account_count"] == 1

            # 4. Attempting to register another Personal account with same phone must be rejected (HTTP 400)
            reg_resp = await client.post("/api/v1/auth/register", json={
                "email": "multi_overflow_test@zenova.id",
                "username": "multi_overflow_user",
                "full_name": "Multi Overflow User",
                "password": "Password123!",
                "account_type": "personal",
                "phone_number": test_phone
            })
            assert reg_resp.status_code == 400
            assert "Personal account already exists" in reg_resp.json()["detail"]

            # 5. Registering a Professional account with same phone must be accepted (HTTP 201)
            reg_resp = await client.post("/api/v1/auth/register", json={
                "email": "multi_prof_test@zenova.id",
                "username": "multi_prof_user",
                "full_name": "Multi Professional User",
                "password": "Password123!",
                "account_type": "professional",
                "phone_number": test_phone
            })
            assert reg_resp.status_code == 201

            # 6. Simulate second verified account in db (Professional)
            user2_id = ObjectId()
            await db.users.insert_one({
                "_id": user2_id,
                "email": "multi_prof_test@zenova.id",
                "username": "multi_prof_user",
                "full_name": "Multi Professional User",
                "account_type": "professional",
                "phone_number": test_phone,
                "is_phone_verified": True,
                "zen_id": "zen_multi_prof",
                "is_active": True,
                "is_verified": True,
                "created_at": now
            })

            # 7. Check eligibility when both personal and professional exist: max_reached must be True
            resp = await client.get(f"/api/v1/auth/phone-eligibility?phone_number={test_phone}")
            assert resp.status_code == 200
            data = resp.json()
            assert data["eligible"] is False
            assert data["max_reached"] is True
            assert len(data["available_types"]) == 0
            assert data["account_count"] == 2
            assert "reached its two-account limit" in data["message"]

            # 8. Attempting 3rd account registration must be rejected with max limit message
            reg_resp_3 = await client.post("/api/v1/auth/register", json={
                "email": "multi_overflow_test@zenova.id",
                "username": "multi_overflow_user",
                "full_name": "User 3 Overflow",
                "password": "Password123!",
                "account_type": "personal",
                "phone_number": test_phone
            })
            assert reg_resp_3.status_code == 400
            assert "two-account limit" in reg_resp_3.json()["detail"]

            # 9. Verify email cannot be reused: registering existing email must be rejected
            dup_email_resp = await client.post("/api/v1/auth/register", json={
                "email": "multi_personal_test@zenova.id",
                "username": "new_random_name",
                "full_name": "Duplicate Email Attempt",
                "password": "Password123!",
                "account_type": "professional"
            })
            assert dup_email_resp.status_code == 400
            assert "already exists" in dup_email_resp.json()["detail"]


