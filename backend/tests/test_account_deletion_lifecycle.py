import pytest
import asyncio
from datetime import datetime, timezone, timedelta
from bson import ObjectId
from unittest.mock import patch, MagicMock

from app.database.client import get_database
from app.services.account_deletion_service import AccountDeletionService
from app.core.otp_service import OTPService
from app.core.security import get_password_hash, create_access_token

@pytest.fixture(autouse=True)
async def setup_db_fixture():
    from app.database.client import connect_to_database, close_database_connection
    await connect_to_database()
    db = get_database()
    if db is None:
        pytest.skip("MongoDB required for integration test")
    yield
    await close_database_connection()

@pytest.mark.asyncio
async def test_account_deletion_lifecycle_e2e():
    db = get_database()
    
    # 1. Setup test user
    email = "lifecycle_test@intellidev.in"
    password = "SecurePassword123!"
    hashed_pwd = get_password_hash(password)
    user_doc = {
        "email": email,
        "username": "lifecycle_user",
        "full_name": "Lifecycle Test User",
        "hashed_password": hashed_pwd,
        "is_active": True,
        "account_status": "active",
        "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc)
    }
    
    await db.users.delete_many({"email": email})
    insert_res = await db.users.insert_one(user_doc)
    user_id = str(insert_res.inserted_id)
    
    # Insert auxiliary records (posts, preferences, tokens)
    await db.posts.insert_one({"author_id": user_id, "content": "Lifecycle post", "created_at": datetime.now(timezone.utc)})
    await db.user_preferences.insert_one({"user_id": user_id, "theme": "midnight-glass"})
    await db.refresh_tokens.insert_one({"user_id": user_id, "token": "mock_refresh_token"})

    try:
        # 2. Test Deletion Request (Day 0)
        del_res = await AccountDeletionService.request_deletion(
            user_id=user_id,
            password=password,
            reason="Testing deletion"
        )
        assert del_res["status"] == "pending_deletion"
        assert del_res["days_remaining"] == 30
        
        # Verify user state in DB
        updated_user = await db.users.find_one({"_id": ObjectId(user_id)})
        assert updated_user["account_status"] == "pending_deletion"
        assert updated_user["is_active"] is False
        assert updated_user["permanent_deletion_at"] is not None

        # Verify refresh tokens and sessions are revoked
        stored_token = await db.refresh_tokens.find_one({"user_id": user_id})
        assert stored_token is None

        # Verify job is scheduled
        job = await db.deletion_jobs.find_one({"user_id": user_id})
        assert job is not None
        assert job["status"] == "scheduled"

        # 3. Test Deletion Status
        status_res = await AccountDeletionService.get_deletion_status(user_id=user_id)
        assert status_res["status"] == "pending_deletion"
        assert status_res["can_recover"] is True
        assert status_res["days_remaining"] >= 29

        # 4. Test Premature Cascading Deletion Call fails closed
        premature_res = await AccountDeletionService.execute_cascading_deletion(user_id=user_id)
        assert premature_res["status"] == "grace_period_active"
        # User must still exist
        assert await db.users.find_one({"_id": ObjectId(user_id)}) is not None

        # 5. Test Recovery (Days 1-29)
        # Clear cooldown if any and generate OTP
        await OTPService.clear_cooldown(email)
        otp_code, otp_gen_ok, _ = await OTPService.create_email_verification_otp(email)
        assert otp_gen_ok is True
        recovery_res = await AccountDeletionService.recover_account(
            email=email,
            password=password,
            otp_code=otp_code
        )
        assert recovery_res["status"] == "recovered"
        assert recovery_res["account_status"] == "active"

        # Verify user state restored in DB
        recovered_user = await db.users.find_one({"_id": ObjectId(user_id)})
        assert recovered_user["account_status"] == "active"
        assert recovered_user["is_active"] is True
        assert "permanent_deletion_at" not in recovered_user or recovered_user.get("permanent_deletion_at") is None

        # Verify job is marked cancelled
        job_after_cancel = await db.deletion_jobs.find_one({"user_id": user_id})
        assert job_after_cancel["status"] == "cancelled"

        # Content must be retained
        assert await db.posts.find_one({"author_id": user_id}) is not None
        assert await db.user_preferences.find_one({"user_id": user_id}) is not None

        # 6. Test Cascading Permanent Deletion after grace period
        # Request deletion again
        await AccountDeletionService.request_deletion(user_id=user_id, password=password)
        # Fast-forward permanent_deletion_at into past
        past_time = datetime.now(timezone.utc) - timedelta(days=1)
        await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": {"permanent_deletion_at": past_time}})
        await db.deletion_jobs.update_one({"user_id": user_id}, {"$set": {"permanent_deletion_at": past_time}})

        # Execute cascading deletion
        cascade_res = await AccountDeletionService.execute_cascading_deletion(user_id=user_id)
        assert cascade_res["status"] == "completed"

        # Verify user and all cascading data are purged
        assert await db.users.find_one({"_id": ObjectId(user_id)}) is None
        assert await db.posts.find_one({"author_id": user_id}) is None
        assert await db.user_preferences.find_one({"user_id": user_id}) is None
        
        # Verify job is marked completed
        final_job = await db.deletion_jobs.find_one({"user_id": user_id})
        assert final_job["status"] == "completed"

    finally:
        # Cleanup test data
        await db.users.delete_many({"email": email})
        await db.deletion_jobs.delete_many({"user_id": user_id})
        await db.posts.delete_many({"author_id": user_id})
        await db.user_preferences.delete_many({"user_id": user_id})
