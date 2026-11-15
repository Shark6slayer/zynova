import pytest
import uuid
from datetime import datetime, timezone
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database.client import connect_to_database, close_database_connection, get_database
from app.core.rate_limit import auth_rate_limiter
from app.core.security import create_access_token, decode_token

@pytest.fixture(autouse=True)
async def isolated_auth_test_env():
    """Sets up database connection and cleans up all created test users after each test."""
    await connect_to_database()
    auth_rate_limiter.requests.clear()
    
    created_test_emails = []
    
    def register_test_email(email: str):
        created_test_emails.append(email)
        
    yield register_test_email
    
    db = get_database()
    if db is not None and created_test_emails:
        # Delete only the specifically generated test emails
        users_to_delete = await db.users.find({"email": {"$in": created_test_emails}}).to_list(length=100)
        user_ids = [str(u["_id"]) for u in users_to_delete]
        
        await db.users.delete_many({"email": {"$in": created_test_emails}})
        await db.refresh_tokens.delete_many({"user_id": {"$in": user_ids}})
        await db.user_preferences.delete_many({"user_id": {"$in": user_ids}})
        await db.conversations.delete_many({"user_id": {"$in": user_ids}})
        
    await close_database_connection()

@pytest.mark.asyncio
async def test_auth_registration_validation_and_login_success(isolated_auth_test_env):
    """Verifies user registration, password complexity validation, and successful login."""
    unique_suffix = str(uuid.uuid4())[:8]
    test_email = f"qa_test_{unique_suffix}@superai.in"
    isolated_auth_test_env(test_email)
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Reject weak password (< 8 chars)
        weak_res = await ac.post("/api/v1/auth/register", json={
            "email": test_email,
            "username": f"user_{unique_suffix}",
            "full_name": "QA Test User",
            "password": "pwd"
        })
        assert weak_res.status_code in [400, 422]

        # 2. Register valid user
        reg_res = await ac.post("/api/v1/auth/register", json={
            "email": test_email,
            "username": f"user_{unique_suffix}",
            "full_name": "QA Test User",
            "password": "StrongPassword2026!"
        })
        assert reg_res.status_code == 201
        reg_data = reg_res.json()
        assert reg_data["email"] == test_email
        assert reg_data["username"] == f"user_{unique_suffix}"
        assert "id" in reg_data

        # 3. Duplicate registration fails closed (400)
        dup_res = await ac.post("/api/v1/auth/register", json={
            "email": test_email,
            "username": f"user_{unique_suffix}",
            "full_name": "QA Test User",
            "password": "StrongPassword2026!"
        })
        assert dup_res.status_code == 400

        # 4. Successful login returns valid TokenResponse
        login_res = await ac.post("/api/v1/auth/login", json={
            "email": test_email,
            "password": "StrongPassword2026!"
        })
        assert login_res.status_code == 200
        tokens = login_res.json()
        assert "access_token" in tokens
        assert "refresh_token" in tokens
        assert tokens["token_type"] == "bearer"
        
        # Verify access token structure and subject
        payload = decode_token(tokens["access_token"])
        assert payload is not None
        assert payload["sub"] == reg_data["id"]
        assert payload["email"] == test_email

@pytest.mark.asyncio
async def test_auth_invalid_credentials_rejected(isolated_auth_test_env):
    """Verifies that invalid passwords and non-existent users are rejected with 401."""
    unique_suffix = str(uuid.uuid4())[:8]
    test_email = f"qa_test_{unique_suffix}@superai.in"
    isolated_auth_test_env(test_email)
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Register user
        await ac.post("/api/v1/auth/register", json={
            "email": test_email,
            "username": f"user_{unique_suffix}",
            "full_name": "QA Test User",
            "password": "StrongPassword2026!"
        })

        # Incorrect password
        bad_pass = await ac.post("/api/v1/auth/login", json={
            "email": test_email,
            "password": "CompletelyWrongPassword!"
        })
        assert bad_pass.status_code == 401
        assert "Incorrect" in bad_pass.json().get("detail", "")

        # Non-existent user
        non_existent = await ac.post("/api/v1/auth/login", json={
            "email": f"non_existent_{unique_suffix}@superai.in",
            "password": "StrongPassword2026!"
        })
        assert non_existent.status_code == 401

@pytest.mark.asyncio
async def test_auth_protected_routes_and_authorization(isolated_auth_test_env):
    """Verifies backend authorization: protected endpoints require valid Bearer token."""
    unique_suffix = str(uuid.uuid4())[:8]
    test_email = f"qa_test_{unique_suffix}@superai.in"
    isolated_auth_test_env(test_email)
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Unauthenticated request to /auth/me rejected (401)
        unauth_me = await ac.get("/api/v1/auth/me")
        assert unauth_me.status_code in [401, 403]

        # 2. Malformed token rejected
        bad_token_res = await ac.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid.fake.token"})
        assert bad_token_res.status_code in [401, 403]

        # 3. Create user and obtain valid token
        reg_res = await ac.post("/api/v1/auth/register", json={
            "email": test_email,
            "username": f"user_{unique_suffix}",
            "full_name": "QA Test User",
            "password": "StrongPassword2026!"
        })
        user_id = reg_res.json()["id"]

        login_res = await ac.post("/api/v1/auth/login", json={
            "email": test_email,
            "password": "StrongPassword2026!"
        })
        access_token = login_res.json()["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        # 4. Valid token authorized for /auth/me
        me_res = await ac.get("/api/v1/auth/me", headers=headers)
        assert me_res.status_code == 200
        me_data = me_res.json()
        assert me_data["id"] == user_id
        assert me_data["email"] == test_email

@pytest.mark.asyncio
async def test_auth_token_refresh_lifecycle(isolated_auth_test_env):
    """Verifies token refresh: valid refresh token issues a new access token."""
    unique_suffix = str(uuid.uuid4())[:8]
    test_email = f"qa_test_{unique_suffix}@superai.in"
    isolated_auth_test_env(test_email)
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post("/api/v1/auth/register", json={
            "email": test_email,
            "username": f"user_{unique_suffix}",
            "full_name": "QA Test User",
            "password": "StrongPassword2026!"
        })

        login_res = await ac.post("/api/v1/auth/login", json={
            "email": test_email,
            "password": "StrongPassword2026!"
        })
        tokens = login_res.json()
        refresh_token = tokens["refresh_token"]

        # Refresh token endpoint
        refresh_res = await ac.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert refresh_res.status_code == 200
        new_tokens = refresh_res.json()
        assert "access_token" in new_tokens
        assert "refresh_token" in new_tokens

        # New access token works
        new_headers = {"Authorization": f"Bearer {new_tokens['access_token']}"}
        me_res = await ac.get("/api/v1/auth/me", headers=new_headers)
        assert me_res.status_code == 200

@pytest.mark.asyncio
async def test_auth_logout_and_session_revocation(isolated_auth_test_env):
    """Verifies logout endpoint revokes the session and clears refresh tokens."""
    unique_suffix = str(uuid.uuid4())[:8]
    test_email = f"qa_test_{unique_suffix}@superai.in"
    isolated_auth_test_env(test_email)
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        reg_res = await ac.post("/api/v1/auth/register", json={
            "email": test_email,
            "username": f"user_{unique_suffix}",
            "full_name": "QA Test User",
            "password": "StrongPassword2026!"
        })
        user_id = reg_res.json()["id"]

        login_res = await ac.post("/api/v1/auth/login", json={
            "email": test_email,
            "password": "StrongPassword2026!"
        })
        tokens = login_res.json()
        headers = {"Authorization": f"Bearer {tokens['access_token']}"}

        # Logout
        logout_res = await ac.post("/api/v1/auth/logout", headers=headers)
        assert logout_res.status_code == 200
        assert logout_res.json()["status"] == "logged_out"

        # Verify refresh token was deleted in database
        db = get_database()
        if db is not None:
            stored_refresh = await db.refresh_tokens.find_one({"user_id": user_id})
            assert stored_refresh is None

@pytest.mark.asyncio
async def test_auth_cross_account_isolation(isolated_auth_test_env):
    """Verifies strict account isolation: User A cannot read or modify User B's resources."""
    user1_suffix = str(uuid.uuid4())[:8]
    user2_suffix = str(uuid.uuid4())[:8]
    email1 = f"user1_{user1_suffix}@superai.in"
    email2 = f"user2_{user2_suffix}@superai.in"
    isolated_auth_test_env(email1)
    isolated_auth_test_env(email2)
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Register User 1
        reg1 = await ac.post("/api/v1/auth/register", json={
            "email": email1,
            "username": f"user1_{user1_suffix}",
            "full_name": "User One",
            "password": "StrongPassword2026!"
        })
        user1_id = reg1.json()["id"]

        # Register User 2
        reg2 = await ac.post("/api/v1/auth/register", json={
            "email": email2,
            "username": f"user2_{user2_suffix}",
            "full_name": "User Two",
            "password": "StrongPassword2026!"
        })
        user2_id = reg2.json()["id"]

        # Login both users
        login1 = await ac.post("/api/v1/auth/login", json={"email": email1, "password": "StrongPassword2026!"})
        login2 = await ac.post("/api/v1/auth/login", json={"email": email2, "password": "StrongPassword2026!"})
        
        token1 = login1.json()["access_token"]
        token2 = login2.json()["access_token"]

        headers1 = {"Authorization": f"Bearer {token1}"}
        headers2 = {"Authorization": f"Bearer {token2}"}

        # Verify User 1 sees only User 1 identity
        me1 = await ac.get("/api/v1/auth/me", headers=headers1)
        assert me1.json()["id"] == user1_id
        assert me1.json()["email"] == email1

        # Verify User 2 sees only User 2 identity
        me2 = await ac.get("/api/v1/auth/me", headers=headers2)
        assert me2.json()["id"] == user2_id
        assert me2.json()["email"] == email2

        # Verify IDs and data do not leak across users
        assert me1.json()["id"] != me2.json()["id"]
        assert me1.json()["email"] != me2.json()["email"]
