import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database.client import connect_to_database, close_database_connection, get_database

@pytest.fixture(autouse=True)
async def setup_db():
    await connect_to_database()
    yield
    await close_database_connection()

@pytest.mark.asyncio
async def test_username_availability_endpoints():
    db = get_database()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Invalid short username
        res = await ac.get("/api/v1/auth/username/availability?username=ab")
        assert res.status_code == 200
        data = res.json()
        assert data["available"] is False
        assert "3 and 30" in data["message"]

        # 2. Reserved username
        res = await ac.get("/api/v1/auth/username/availability?username=admin")
        assert res.status_code == 200
        data = res.json()
        assert data["available"] is False
        assert "reserved" in data["message"]

        # 3. Available novel username
        unique_test_user = "zenova_hero_99182"
        await db.users.delete_many({"username": unique_test_user})
        res = await ac.get(f"/api/v1/auth/username/availability?username={unique_test_user}")
        assert res.status_code == 200
        data = res.json()
        assert data["available"] is True
        assert "available" in data["message"].lower()

        # 4. Suggestions endpoint - must NOT automatically contain zen_ or zen
        res = await ac.get("/api/v1/auth/username/suggestions?username=karuppasamy")
        assert res.status_code == 200
        sugg_data = res.json()
        assert "suggestions" in sugg_data
        assert len(sugg_data["suggestions"]) > 0
        for s in sugg_data["suggestions"]:
            assert not s.startswith("zen_"), f"Suggestion {s} should not start with zen_"
            assert "_zen" not in s, f"Suggestion {s} should not contain _zen"

        # 5. Case-insensitive uniqueness check
        await db.users.delete_many({"username": "karuppasamy"})
        await db.users.insert_one({
            "email": "karuppasamy@zenova.in",
            "username": "karuppasamy",
            "zen_id": "karuppasamy",
            "full_name": "Karuppasamy",
            "is_active": True,
            "is_verified": True,
        })
        # Check uppercase or mixed case
        res_case = await ac.get("/api/v1/auth/username/availability?username=Karuppasamy")
        assert res_case.status_code == 200
        assert res_case.json()["available"] is False
        assert "already taken" in res_case.json()["message"].lower()

@pytest.mark.asyncio
async def test_set_username_atomic():
    from app.core.security import create_access_token
    db = get_database()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        test_email = "zenid_test_user@zenova.in"
        other_email = "other_guy@zenova.in"
        # Seed users in db
        await db.users.delete_many({"email": {"$in": [test_email, other_email]}})
        ins = await db.users.insert_one({
            "email": test_email,
            "username": "temp_user_initial",
            "full_name": "ZenID Tester",
            "is_active": True,
            "is_verified": True,
        })
        tok = create_access_token({"sub": str(ins.inserted_id), "email": test_email, "type": "access"})
        headers = {"Authorization": f"Bearer {tok}"}

        ins_other = await db.users.insert_one({
            "email": other_email,
            "username": "other_guy_init",
            "full_name": "Other Guy",
            "is_active": True,
            "is_verified": True,
        })
        tok_other = create_access_token({"sub": str(ins_other.inserted_id), "email": other_email, "type": "access"})
        headers_other = {"Authorization": f"Bearer {tok_other}"}

        # Unauthenticated request -> 401
        res_unauth = await ac.post("/api/v1/auth/username/set", json={"email": test_email, "username": "unauth_name"})
        assert res_unauth.status_code == 401

        # Cross-user email modification attempt -> 403
        res_cross = await ac.post("/api/v1/auth/username/set", headers=headers_other, json={"email": test_email, "username": "hijack_name"})
        assert res_cross.status_code == 403

        # Claim novel username
        new_username = "sovereign_tester_99"
        await db.users.delete_many({"username": new_username})

        res = await ac.post("/api/v1/auth/username/set", headers=headers, json={
            "email": test_email,
            "username": new_username
        })
        assert res.status_code == 200
        resp_data = res.json()
        assert resp_data["status"] == "success"
        assert resp_data["username"] == new_username
        assert resp_data["zen_id"] == new_username
        assert not resp_data["zen_id"].startswith("zen_")

        # Verify db updated exactly with user's chosen username
        user_doc = await db.users.find_one({"email": test_email})
        assert user_doc["username"] == new_username
        assert user_doc["zen_id"] == new_username
        assert not user_doc["zen_id"].startswith("zen_")

        # Attempt to claim with another account -> should fail with 409 Conflict
        res_conflict = await ac.post("/api/v1/auth/username/set", headers=headers_other, json={
            "email": other_email,
            "username": new_username
        })
        assert res_conflict.status_code == 409

        # Cleanup
        await db.users.delete_many({"email": {"$in": [test_email, other_email]}})
        await db.users.delete_many({"username": new_username})
        await db.users.delete_many({"email": "karuppasamy@zenova.in"})
