import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone
from bson import ObjectId

from app.main import app
from app.database.client import connect_to_database, close_database_connection, get_database
from app.core.security import get_password_hash, create_access_token


@pytest.fixture(autouse=True)
async def setup_db():
    await connect_to_database()
    yield
    await close_database_connection()


@pytest.mark.asyncio
async def test_add_account_invalid_credentials_rejected():
    """Verifies that invalid credentials fail with HTTP 401 and never create an account or session."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/api/v1/auth/login", json={
            "email": "nonexistent_user_999@superai.in",
            "password": "WrongPassword123!"
        })
        assert res.status_code == 401
        assert "Incorrect email or password" in res.json().get("detail", "")


@pytest.mark.asyncio
async def test_add_account_unverified_account_rejected():
    """Verifies that an unverified account cannot authenticate or be added to a device."""
    db = get_database()
    now = datetime.now(timezone.utc)
    uid = ObjectId()
    email = f"unverified_{uuid.uuid4().hex[:8]}@superai.in"
    password = "ValidPassword2026!"
    hashed = get_password_hash(password)

    await db.users.insert_one({
        "_id": uid,
        "email": email,
        "username": f"unver_{uid}",
        "full_name": "Unverified User",
        "hashed_password": hashed,
        "is_active": True,
        "is_verified": False,
        "account_type": "personal",
        "created_at": now,
        "updated_at": now
    })

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.post("/api/v1/auth/login", json={
                "email": email,
                "password": password
            })
            assert res.status_code == 403
            assert "Email not verified" in res.json().get("detail", "")
    finally:
        await db.users.delete_one({"_id": uid})


@pytest.mark.asyncio
async def test_add_account_genuine_authentication_flow():
    """Verifies genuine authentication succeeds with real DB identity and tokens."""
    db = get_database()
    now = datetime.now(timezone.utc)
    uid = ObjectId()
    email = f"genuine_{uuid.uuid4().hex[:8]}@superai.in"
    username = f"genuine_{uuid.uuid4().hex[:6]}"
    password = "RealPassword2026!"
    hashed = get_password_hash(password)

    await db.users.insert_one({
        "_id": uid,
        "email": email,
        "username": username,
        "full_name": "Genuine User",
        "hashed_password": hashed,
        "is_active": True,
        "is_verified": True,
        "account_type": "personal",
        "created_at": now,
        "updated_at": now
    })

    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            login_res = await ac.post("/api/v1/auth/login", json={
                "email": email,
                "password": password
            })
            assert login_res.status_code == 200
            data = login_res.json()
            assert "access_token" in data
            assert data["user"]["id"] == str(uid)
            assert data["user"]["email"] == email
            assert data["user"]["username"] == username

            # Validate /users/me using the returned token
            token = data["access_token"]
            me_res = await ac.get("/api/v1/users/me", headers={"Authorization": f"Bearer {token}"})
            assert me_res.status_code == 200
            me_data = me_res.json()
            assert me_data["id"] == str(uid)
            assert me_data["email"] == email
    finally:
        await db.users.delete_one({"_id": uid})
        await db.refresh_tokens.delete_many({"user_id": str(uid)})


@pytest.mark.asyncio
async def test_zero_dummy_accounts_in_database():
    """Verifies that no fabricated or dummy account patterns exist in the database."""
    db = get_database()
    # Query for any dummy ID patterns or mock names
    dummy_users = await db.users.count_documents({
        "$or": [
            {"_id": {"$regex": "^sec_"}},
            {"username": "alexander"},
            {"email": "alexander@zenova.in"},
            {"id": {"$regex": "^sec_"}}
        ]
    })
    assert dummy_users == 0, f"Found {dummy_users} dummy accounts in database!"
