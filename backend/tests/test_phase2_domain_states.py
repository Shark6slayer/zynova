import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database.client import connect_to_database, close_database_connection, get_database
from app.core.rate_limit import (
    auth_rate_limiter,
    chat_rate_limiter,
    social_post_rate_limiter,
    food_order_rate_limiter,
    payment_rate_limiter,
    balance_enquiry_rate_limiter
)

@pytest.fixture(autouse=True)
async def phase2_test_environment():
    """Sets up database connection and resets rate limiters for isolated Phase 2 state tests."""
    await connect_to_database()
    auth_rate_limiter.requests.clear()
    chat_rate_limiter.requests.clear()
    social_post_rate_limiter.requests.clear()
    food_order_rate_limiter.requests.clear()
    payment_rate_limiter.requests.clear()
    balance_enquiry_rate_limiter.requests.clear()

    created_test_emails = []

    def track_email(email: str):
        created_test_emails.append(email)

    yield track_email

    db = get_database()
    if db is not None and created_test_emails:
        users = await db.users.find({"email": {"$in": created_test_emails}}).to_list(length=100)
        user_ids = [str(u["_id"]) for u in users]

        await db.users.delete_many({"email": {"$in": created_test_emails}})
        await db.refresh_tokens.delete_many({"user_id": {"$in": user_ids}})
        await db.user_preferences.delete_many({"user_id": {"$in": user_ids}})
        await db.conversations.delete_many({"user_id": {"$in": user_ids}})
        await db.chat_rooms.delete_many({"participants": {"$in": user_ids}})
        await db.food_orders.delete_many({"user_id": {"$in": user_ids}})
        await db.bank_accounts.delete_many({"user_id": {"$in": user_ids}})
        await db.payment_transactions.delete_many({"sender_id": {"$in": user_ids}})

    await close_database_connection()


@pytest.mark.asyncio
async def test_chat_empty_and_unauthorized_states(phase2_test_environment):
    """Verifies chat module handling of empty conversations, unauthorized message access, and invalid IDs."""
    suffix = str(uuid.uuid4())[:8]
    email = f"chat_qa_{suffix}@superai.in"
    phase2_test_environment(email)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Unauthenticated access to chat conversations rejected
        unauth_rooms = await ac.get("/api/v1/chat/conversations")
        assert unauth_rooms.status_code in [401, 403]

        # 2. Register and login
        reg_res = await ac.post("/api/v1/auth/register", json={
            "email": email,
            "username": f"chat_user_{suffix}",
            "full_name": "Chat QA User",
            "password": "StrongPassword2026!"
        })
        assert reg_res.status_code == 201

        login_res = await ac.post("/api/v1/auth/login", json={"email": email, "password": "StrongPassword2026!"})
        headers = {"Authorization": f"Bearer {login_res.json()['access_token']}"}

        # 3. New user gets an empty list of conversations (Empty State)
        rooms_res = await ac.get("/api/v1/chat/conversations", headers=headers)
        assert rooms_res.status_code == 200
        assert isinstance(rooms_res.json(), list)
        assert len(rooms_res.json()) == 0

        # 4. Accessing non-existent conversation returns 404
        non_existent_room = await ac.get("/api/v1/chat/conversations/000000000000000000000000/messages", headers=headers)
        assert non_existent_room.status_code in [400, 404]


@pytest.mark.asyncio
async def test_social_feed_empty_state_and_post_reporting(phase2_test_environment):
    """Verifies social feed initial/empty state, post creation boundaries, and reporting validation."""
    suffix = str(uuid.uuid4())[:8]
    email = f"social_qa_{suffix}@superai.in"
    phase2_test_environment(email)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Register and login
        await ac.post("/api/v1/auth/register", json={
            "email": email,
            "username": f"social_user_{suffix}",
            "full_name": "Social QA User",
            "password": "StrongPassword2026!"
        })
        login = await ac.post("/api/v1/auth/login", json={"email": email, "password": "StrongPassword2026!"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        # 1. Feed returns list cleanly (even if empty or global seed)
        feed_res = await ac.get("/api/v1/social/feed", headers=headers)
        assert feed_res.status_code == 200
        assert isinstance(feed_res.json(), list)

        # 2. Cannot report non-existent post (404)
        report_res = await ac.post(
            "/api/v1/social/posts/000000000000000000000000/report",
            headers=headers,
            json={"reason": "spam", "details": "Testing non-existent post reporting"}
        )
        assert report_res.status_code in [400, 404]

        # 3. Empty post content rejected (validation check)
        empty_post_res = await ac.post(
            "/api/v1/social/posts",
            headers=headers,
            json={"content": "   "}
        )
        assert empty_post_res.status_code in [400, 422]


@pytest.mark.asyncio
async def test_food_dining_discovery_and_order_validation(phase2_test_environment):
    """Verifies restaurant catalog discovery and empty cart order rejection."""
    suffix = str(uuid.uuid4())[:8]
    email = f"food_qa_{suffix}@superai.in"
    phase2_test_environment(email)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # Register and login
        await ac.post("/api/v1/auth/register", json={
            "email": email,
            "username": f"food_user_{suffix}",
            "full_name": "Food QA User",
            "password": "StrongPassword2026!"
        })
        login = await ac.post("/api/v1/auth/login", json={"email": email, "password": "StrongPassword2026!"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        # 1. Restaurants catalog returns list cleanly
        rest_res = await ac.get("/api/v1/food/restaurants", headers=headers)
        assert rest_res.status_code == 200
        assert isinstance(rest_res.json(), list)

        # 2. Order with empty items list rejected (validation check)
        empty_order_res = await ac.post(
            "/api/v1/food/orders",
            headers=headers,
            json={
                "restaurant_id": "rest_1",
                "items": [],
                "delivery_address": "Bangalore Central",
                "payment_mode": "upi"
            }
        )
        assert empty_order_res.status_code in [400, 422]


@pytest.mark.asyncio
async def test_settings_language_preferences_and_invalid_codes(phase2_test_environment):
    """Verifies language preferences persistence and rejection of unsupported language codes."""
    suffix = str(uuid.uuid4())[:8]
    email = f"pref_qa_{suffix}@superai.in"
    phase2_test_environment(email)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post("/api/v1/auth/register", json={
            "email": email,
            "username": f"pref_user_{suffix}",
            "full_name": "Preferences QA User",
            "password": "StrongPassword2026!"
        })
        login = await ac.post("/api/v1/auth/login", json={"email": email, "password": "StrongPassword2026!"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        # 1. Update valid Indic language (e.g., Tamil 'ta')
        pref_res = await ac.put(
            "/api/v1/preferences",
            headers=headers,
            json={"language": "ta", "theme": "midnight-glass", "appearanceMode": "dark"}
        )
        assert pref_res.status_code == 200
        assert pref_res.json().get("language") == "ta"

        # 2. Unsupported fake language code rejected
        bad_lang_res = await ac.put(
            "/api/v1/preferences",
            headers=headers,
            json={"language": "xyz_invalid", "theme": "midnight-glass", "appearanceMode": "dark"}
        )
        assert bad_lang_res.status_code in [400, 422]


@pytest.mark.asyncio
async def test_payments_sandbox_security_and_masking(phase2_test_environment):
    """Verifies payment sandbox security: account masking and zero exposure of plaintext sensitive numbers."""
    suffix = str(uuid.uuid4())[:8]
    email = f"pay_qa_{suffix}@superai.in"
    phase2_test_environment(email)

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        await ac.post("/api/v1/auth/register", json={
            "email": email,
            "username": f"pay_user_{suffix}",
            "full_name": "Payment QA User",
            "password": "StrongPassword2026!"
        })
        login = await ac.post("/api/v1/auth/login", json={"email": email, "password": "StrongPassword2026!"})
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        # Link bank account
        raw_account_number = "98765432109876"
        link_res = await ac.post(
            "/api/v1/payments/accounts",
            headers=headers,
            json={
                "bank_name": "State Bank of India",
                "account_number": raw_account_number,
                "ifsc_code": "SBIN0001234",
                "account_type": "savings",
                "nickname": "Primary SBI"
            }
        )
        assert link_res.status_code == 201
        account_data = link_res.json()

        # Strict security assertions: Plaintext account number must NEVER be returned
        assert "masked_account_number" in account_data
        assert raw_account_number not in str(account_data)
        assert account_data["masked_account_number"].startswith("••••")
