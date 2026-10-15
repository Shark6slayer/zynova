import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database.client import connect_to_database, close_database_connection, get_database
from app.core.rate_limit import auth_rate_limiter

@pytest.fixture(autouse=True)
async def init_db():
    await connect_to_database()
    auth_rate_limiter.requests.clear()
    yield
    db = get_database()
    if db is not None:
        await db.users.delete_many({"email": {"$in": ["test_e2e@superai.in", "other_user@superai.in"]}})
        await db.user_preferences.delete_many({"user_id": {"$in": ["test_e2e_id", "other_id"]}})
        await db.conversations.delete_many({"title": "Indic NLP Research"})
    await close_database_connection()

@pytest.mark.asyncio
async def test_full_auth_and_preferences_lifecycle():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Register User
        reg_payload = {
            "email": "test_e2e@superai.in",
            "username": "e2e_user",
            "full_name": "E2E Test User",
            "password": "SecurePassword123!"
        }
        reg_res = await ac.post("/api/v1/auth/register", json=reg_payload)
        assert reg_res.status_code == 201
        user_data = reg_res.json()
        assert user_data["email"] == "test_e2e@superai.in"
        assert "id" in user_data

        # 2. Duplicate registration rejected
        dup_res = await ac.post("/api/v1/auth/register", json=reg_payload)
        assert dup_res.status_code == 400

        # 3. Weak password rejected
        weak_res = await ac.post("/api/v1/auth/register", json={
            "email": "weak@superai.in",
            "username": "weak_user",
            "full_name": "Weak User",
            "password": "simple"
        })
        assert weak_res.status_code in [400, 422]


        # 4. Invalid Login
        bad_login = await ac.post("/api/v1/auth/login", json={
            "email": "test_e2e@superai.in",
            "password": "WrongPassword!"
        })
        assert bad_login.status_code == 401

        # 5. Valid Login User
        login_res = await ac.post("/api/v1/auth/login", json={
            "email": "test_e2e@superai.in",
            "password": "SecurePassword123!"
        })
        assert login_res.status_code == 200
        token_data = login_res.json()
        assert "access_token" in token_data
        assert "refresh_token" in token_data
        token = token_data["access_token"]
        refresh_token = token_data["refresh_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 6. Access Me
        me_res = await ac.get("/api/v1/auth/me", headers=headers)
        assert me_res.status_code == 200
        assert me_res.json()["username"] == "e2e_user"

        # 7. Update User Profile (Full Name & Bio)
        update_profile_res = await ac.patch("/api/v1/users/me", json={
            "full_name": "E2E Updated Name",
            "bio": "Researching Indian Sovereign AI Systems"
        }, headers=headers)
        assert update_profile_res.status_code == 200
        updated_profile = update_profile_res.json()
        assert updated_profile["full_name"] == "E2E Updated Name"
        assert updated_profile["bio"] == "Researching Indian Sovereign AI Systems"

        # 8. Refresh Token Rotation
        ref_res = await ac.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert ref_res.status_code == 200
        new_token_data = ref_res.json()
        assert "access_token" in new_token_data
        new_token = new_token_data["access_token"]
        headers = {"Authorization": f"Bearer {new_token}"}

        # 9. Old refresh token should now be superseded
        old_ref_res = await ac.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert old_ref_res.status_code == 401

        # 10. Fetch Preferences
        pref_res = await ac.get("/api/v1/preferences", headers=headers)
        assert pref_res.status_code == 200
        prefs = pref_res.json()
        assert prefs["theme"] == "midnight-glass"

        # 11. Update Preferences
        prefs["theme"] = "indian-heritage"
        prefs["language"] = "ta"
        update_pref_res = await ac.put("/api/v1/preferences", json=prefs, headers=headers)
        assert update_pref_res.status_code == 200
        assert update_pref_res.json()["theme"] == "indian-heritage"
        assert update_pref_res.json()["language"] == "ta"

        # 12. Cross-user isolation: register a second user
        other_payload = {
            "email": "other_user@superai.in",
            "username": "other_user",
            "full_name": "Other User",
            "password": "SecurePassword456!"
        }
        other_reg = await ac.post("/api/v1/auth/register", json=other_payload)
        assert other_reg.status_code == 201

        other_login = await ac.post("/api/v1/auth/login", json={
            "email": "other_user@superai.in",
            "password": "SecurePassword456!"
        })
        other_token = other_login.json()["access_token"]
        other_headers = {"Authorization": f"Bearer {other_token}"}

        other_me = await ac.get("/api/v1/auth/me", headers=other_headers)
        assert other_me.json()["username"] == "other_user"
        assert other_me.json()["id"] != user_data["id"]

        # 13. Create a Conversation as user 1
        conv_res = await ac.post("/api/v1/conversations", json={
            "title": "Indic NLP Research",
            "model": "SUPER Reasoning (CoT)"
        }, headers=headers)
        assert conv_res.status_code == 201
        conv_id = conv_res.json()["id"]

        # 14. User 2 cannot access or delete User 1's conversation
        user2_del_conv = await ac.delete(f"/api/v1/conversations/{conv_id}", headers=other_headers)
        assert user2_del_conv.status_code == 404

        # 15. User 1 deletes their own conversation
        user1_del_conv = await ac.delete(f"/api/v1/conversations/{conv_id}", headers=headers)
        assert user1_del_conv.status_code == 200

        # 16. Logout User 1
        logout_res = await ac.post("/api/v1/auth/logout", headers=headers)
        assert logout_res.status_code == 200

        # 17. Safe Account Deletion with Password Re-authentication
        # Wrong password rejected
        bad_delete = await ac.request("DELETE", "/api/v1/users/me", json={"password": "WrongPassword"}, headers=other_headers)
        assert bad_delete.status_code == 400

        # Correct password deletes account
        good_delete = await ac.request("DELETE", "/api/v1/users/me", json={"password": "SecurePassword456!"}, headers=other_headers)
        assert good_delete.status_code == 200
        assert good_delete.json()["status"] == "deleted"

        # Verify User 2 no longer exists
        deleted_login = await ac.post("/api/v1/auth/login", json={
            "email": "other_user@superai.in",
            "password": "SecurePassword456!"
        })
        assert deleted_login.status_code == 401
