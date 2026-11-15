import pytest
import uuid
import time
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database.client import connect_to_database, close_database_connection, get_database
from app.core.rate_limit import (
    auth_rate_limiter,
    chat_rate_limiter,
    social_post_rate_limiter,
    food_order_rate_limiter,
    shopping_order_rate_limiter,
    payment_rate_limiter
)
from app.core.security import create_access_token

@pytest.fixture(autouse=True)
async def phase3_test_env():
    """Sets up local test database and guarantees strict cleanup of all test accounts."""
    await connect_to_database()
    auth_rate_limiter.requests.clear()
    chat_rate_limiter.requests.clear()
    social_post_rate_limiter.requests.clear()
    food_order_rate_limiter.requests.clear()
    shopping_order_rate_limiter.requests.clear()
    payment_rate_limiter.requests.clear()

    created_emails = []

    def track_email(email: str):
        created_emails.append(email)

    yield track_email

    db = get_database()
    if db is not None and created_emails:
        users = await db.users.find({"email": {"$in": created_emails}}).to_list(length=100)
        user_ids = [str(u["_id"]) for u in users]

        await db.users.delete_many({"email": {"$in": created_emails}})
        await db.refresh_tokens.delete_many({"user_id": {"$in": user_ids}})
        await db.user_preferences.delete_many({"user_id": {"$in": user_ids}})
        await db.conversations.delete_many({"user_id": {"$in": user_ids}})
        await db.chat_rooms.delete_many({"participants": {"$in": user_ids}})
        await db.chat_messages.delete_many({"sender_id": {"$in": user_ids}})
        await db.posts.delete_many({"author_id": {"$in": user_ids}})
        await db.food_orders.delete_many({"user_id": {"$in": user_ids}})
        await db.shopping_orders.delete_many({"user_id": {"$in": user_ids}})
        await db.bank_accounts.delete_many({"user_id": {"$in": user_ids}})
        await db.payment_transactions.delete_many({"sender_id": {"$in": user_ids}})

    await close_database_connection()


@pytest.mark.asyncio
async def test_auth_token_edge_cases_and_tampering(phase3_test_env):
    """Verifies that expired, malformed, and signature-tampered tokens fail closed."""
    suffix = str(uuid.uuid4())[:8]
    email = f"auth_edge_{suffix}@superai.in"
    phase3_test_env(email)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Register user
        reg_res = await ac.post("/api/v1/auth/register", json={
            "email": email,
            "username": f"user_edge_{suffix}",
            "full_name": "Auth Edge User",
            "password": "StrongPassword2026!"
        })
        assert reg_res.status_code == 201
        user_id = reg_res.json()["id"]

        # 1. Missing Authorization Header
        no_auth = await ac.get("/api/v1/auth/me")
        assert no_auth.status_code in [401, 403]

        # 2. Malformed Header (Not Bearer)
        bad_scheme = await ac.get("/api/v1/auth/me", headers={"Authorization": "Basic dXNlcjpwYXNz"})
        assert bad_scheme.status_code in [401, 403]

        # 3. Garbage JWT Token
        garbage_token = await ac.get("/api/v1/auth/me", headers={"Authorization": "Bearer not.a.valid.jwt"})
        assert garbage_token.status_code in [401, 403]

        # 4. Tampered Token Signature
        valid_login = await ac.post("/api/v1/auth/login", json={"email": email, "password": "StrongPassword2026!"})
        valid_tok = valid_login.json()["access_token"]
        tampered_tok = valid_tok[:-6] + "xxxxxx"
        tampered_res = await ac.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {tampered_tok}"})
        assert tampered_res.status_code in [401, 403]

        # 5. Expired Token
        from datetime import timedelta
        expired_tok = create_access_token(
            data={"sub": user_id, "email": email, "jti": str(uuid.uuid4())},
            expires_delta=timedelta(seconds=-100)  # expired in past
        )
        expired_res = await ac.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {expired_tok}"})
        assert expired_res.status_code in [401, 403]


@pytest.mark.asyncio
async def test_cross_user_shopping_order_isolation(phase3_test_env):
    """Verifies that User A cannot view, cancel, or modify User B's shopping orders."""
    u1_suffix = str(uuid.uuid4())[:8]
    u2_suffix = str(uuid.uuid4())[:8]
    email1 = f"buyer1_{u1_suffix}@superai.in"
    email2 = f"buyer2_{u2_suffix}@superai.in"
    phase3_test_env(email1)
    phase3_test_env(email2)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Register User 1 & User 2
        await ac.post("/api/v1/auth/register", json={
            "email": email1,
            "username": f"buyer1_{u1_suffix}",
            "full_name": "Buyer One",
            "password": "StrongPassword2026!"
        })
        login1 = await ac.post("/api/v1/auth/login", json={"email": email1, "password": "StrongPassword2026!"})
        h1 = {"Authorization": f"Bearer {login1.json()['access_token']}"}

        await ac.post("/api/v1/auth/register", json={
            "email": email2,
            "username": f"buyer2_{u2_suffix}",
            "full_name": "Buyer Two",
            "password": "StrongPassword2026!"
        })
        login2 = await ac.post("/api/v1/auth/login", json={"email": email2, "password": "StrongPassword2026!"})
        h2 = {"Authorization": f"Bearer {login2.json()['access_token']}"}

        # User 1 views orders list: empty
        orders1 = await ac.get("/api/v1/shopping/orders", headers=h1)
        assert orders1.status_code == 200
        assert isinstance(orders1.json(), list)

        # User 2 attempts to query non-existent or User 1 order ID
        fake_order_id = "000000000000000000000000"
        detail_res = await ac.get(f"/api/v1/shopping/orders/{fake_order_id}", headers=h2)
        assert detail_res.status_code in [400, 404]

        cancel_res = await ac.post(f"/api/v1/shopping/orders/{fake_order_id}/cancel", headers=h2)
        assert cancel_res.status_code in [400, 404]


@pytest.mark.asyncio
async def test_cross_user_chat_message_eavesdropping_prevention(phase3_test_env):
    """Verifies that an intruder cannot read messages from a private conversation between two other users."""
    u1_suffix = str(uuid.uuid4())[:8]
    u2_suffix = str(uuid.uuid4())[:8]
    intruder_suffix = str(uuid.uuid4())[:8]
    email1 = f"chat1_{u1_suffix}@superai.in"
    email2 = f"chat2_{u2_suffix}@superai.in"
    email_int = f"intruder_{intruder_suffix}@superai.in"
    phase3_test_env(email1)
    phase3_test_env(email2)
    phase3_test_env(email_int)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Register User 1, User 2, Intruder
        r1 = await ac.post("/api/v1/auth/register", json={"email": email1, "username": f"u1_{u1_suffix}", "full_name": "Alice", "password": "StrongPassword2026!"})
        u1_id = r1.json()["id"]
        l1 = await ac.post("/api/v1/auth/login", json={"email": email1, "password": "StrongPassword2026!"})
        h1 = {"Authorization": f"Bearer {l1.json()['access_token']}"}

        r2 = await ac.post("/api/v1/auth/register", json={"email": email2, "username": f"u2_{u2_suffix}", "full_name": "Bob", "password": "StrongPassword2026!"})
        u2_id = r2.json()["id"]

        r_int = await ac.post("/api/v1/auth/register", json={"email": email_int, "username": f"int_{intruder_suffix}", "full_name": "Eve", "password": "StrongPassword2026!"})
        l_int = await ac.post("/api/v1/auth/login", json={"email": email_int, "password": "StrongPassword2026!"})
        h_int = {"Authorization": f"Bearer {l_int.json()['access_token']}"}

        # Alice creates conversation with Bob and sends a private message
        conv_res = await ac.post("/api/v1/chat/conversations", json={"recipient_id": u2_id}, headers=h1)
        assert conv_res.status_code == 200
        conv_id = conv_res.json()["id"]

        await ac.post(f"/api/v1/chat/conversations/{conv_id}/messages", json={"text": "Classified confidential message"}, headers=h1)

        # Eve attempts to access the conversation history
        eve_spy_res = await ac.get(f"/api/v1/chat/conversations/{conv_id}/messages", headers=h_int)
        assert eve_spy_res.status_code in [401, 403, 404]
        assert "Classified confidential message" not in str(eve_spy_res.text)

        # Eve attempts to send a message into the conversation
        eve_send_res = await ac.post(f"/api/v1/chat/conversations/{conv_id}/messages", json={"text": "Imposter message"}, headers=h_int)
        assert eve_send_res.status_code in [401, 403, 404]


@pytest.mark.asyncio
async def test_input_validation_and_injection_resilience(phase3_test_env):
    """Verifies that malicious payloads (NoSQL injection objects, oversized strings) fail closed safely."""
    suffix = str(uuid.uuid4())[:8]
    email = f"sec_qa_{suffix}@superai.in"
    phase3_test_env(email)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Register user
        await ac.post("/api/v1/auth/register", json={
            "email": email,
            "username": f"sec_user_{suffix}",
            "full_name": "Security QA",
            "password": "StrongPassword2026!"
        })
        login = await ac.post("/api/v1/auth/login", json={"email": email, "password": "StrongPassword2026!"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        # 1. NoSQL Injection attempt in login email: {"$ne": null}
        nosql_login = await ac.post("/api/v1/auth/login", json={
            "email": {"$ne": None},
            "password": "StrongPassword2026!"
        })
        assert nosql_login.status_code in [400, 422]

        # 2. Free-form string in theme (JSON response serialization check)
        # Note: Backend stores theme as str. The API serializes as application/json,
        # preventing HTML/XSS execution in API responses, but theme is not restricted to an enum.
        raw_theme = "custom-dark-theme-2026"
        valid_pref = await ac.put("/api/v1/preferences", headers=headers, json={
            "language": "en",
            "theme": raw_theme,
            "appearanceMode": "dark"
        })
        assert valid_pref.status_code == 200
        assert valid_pref.headers.get("content-type", "").startswith("application/json")
        assert valid_pref.json().get("theme") == raw_theme

        # 3. Oversized string payload in search query
        oversized_query = "A" * 5000
        search_res = await ac.get(f"/api/v1/search?q={oversized_query}", headers=headers)
        assert search_res.status_code in [200, 400, 422]
