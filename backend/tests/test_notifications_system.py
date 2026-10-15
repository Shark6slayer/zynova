import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database.client import connect_to_database, close_database_connection, get_database
from app.core.rate_limit import auth_rate_limiter, chat_rate_limiter, social_post_rate_limiter

@pytest.fixture(autouse=True)
async def init_notification_test_db():
    await connect_to_database()
    auth_rate_limiter.requests.clear()
    chat_rate_limiter.requests.clear()
    social_post_rate_limiter.requests.clear()
    yield
    db = get_database()
    if db is not None:
        await db.users.delete_many({"username": {"$in": ["notif_user_a", "notif_user_b"]}})
        await db.notifications.delete_many({"user_id": {"$in": ["test_uid_a", "test_uid_b"]}})
        await db.chat_rooms.delete_many({"participants": {"$in": ["notif_user_a", "notif_user_b"]}})
        await db.posts.delete_many({"author_username": {"$in": ["notif_user_a", "notif_user_b"]}})
    await close_database_connection()

@pytest.mark.asyncio
async def test_notifications_lifecycle_and_events():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        db = get_database()
        if db is not None:
            await db.users.delete_many({"username": {"$in": ["notif_user_a", "notif_user_b"]}})

        # 1. Register User A & User B
        res_a = await client.post("/api/v1/auth/register", json={
            "email": "notif_a@superai.in",
            "username": "notif_user_a",
            "full_name": "Notification User A",
            "password": "Password123!"
        })
        assert res_a.status_code == 201
        user_a_id = res_a.json()["id"]

        login_a = await client.post("/api/v1/auth/login", json={
            "email": "notif_a@superai.in",
            "password": "Password123!"
        })
        h_a = {"Authorization": f"Bearer {login_a.json()['access_token']}"}

        res_b = await client.post("/api/v1/auth/register", json={
            "email": "notif_b@superai.in",
            "username": "notif_user_b",
            "full_name": "Notification User B",
            "password": "Password123!"
        })
        assert res_b.status_code == 201
        user_b_id = res_b.json()["id"]

        login_b = await client.post("/api/v1/auth/login", json={
            "email": "notif_b@superai.in",
            "password": "Password123!"
        })
        h_b = {"Authorization": f"Bearer {login_b.json()['access_token']}"}

        # User A initially has 0 notifications
        count_a = await client.get("/api/v1/notifications/unread-count", headers=h_a)
        assert count_a.status_code == 200
        assert count_a.json()["unread_count"] == 0

        # 2. Event Integration: User B follows User A -> Generates notification for User A
        follow_res = await client.post(f"/api/v1/social/profiles/{user_a_id}/follow", headers=h_b)
        assert follow_res.status_code == 200

        # Check User A's unread count
        count_a2 = await client.get("/api/v1/notifications/unread-count", headers=h_a)
        assert count_a2.json()["unread_count"] == 1

        # Check User A's notification list
        list_a = await client.get("/api/v1/notifications", headers=h_a)
        assert list_a.status_code == 200
        data_a = list_a.json()
        assert data_a["total"] == 1
        assert data_a["unread_count"] == 1
        notif = data_a["notifications"][0]
        assert notif["category"] == "social"
        assert notif["event_type"] == "social_follow"
        assert "started following you" in notif["title"]
        assert notif["metadata"]["navigation_target"] == f"social:user:{user_b_id}"
        notif_id = notif["id"]

        # User B should NOT have any notifications (no self-notifications)
        count_b = await client.get("/api/v1/notifications/unread-count", headers=h_b)
        assert count_b.json()["unread_count"] == 0

        # 3. Duplicate event idempotency: repeating follow action does NOT create duplicate notification
        follow_res2 = await client.post(f"/api/v1/social/profiles/{user_a_id}/follow", headers=h_b)
        assert follow_res2.status_code == 200
        count_a_repeat = await client.get("/api/v1/notifications/unread-count", headers=h_a)
        assert count_a_repeat.json()["unread_count"] == 1

        # 4. Event Integration: User A creates a post, User B likes it -> Generates like notification for User A
        post_res = await client.post("/api/v1/social/posts", json={
            "content": "Exciting updates on sovereign open source AI!"
        }, headers=h_a)
        assert post_res.status_code == 201
        post_id = post_res.json()["id"]

        like_res = await client.post(f"/api/v1/social/posts/{post_id}/like", headers=h_b)
        assert like_res.status_code == 200

        # User A unread count should now be 2
        count_a3 = await client.get("/api/v1/notifications/unread-count", headers=h_a)
        assert count_a3.json()["unread_count"] == 2

        # 5. Event Integration: User A likes their OWN post -> Should NOT generate self-notification
        like_self = await client.post(f"/api/v1/social/posts/{post_id}/like", headers=h_a)
        assert like_self.status_code == 200
        count_a_self = await client.get("/api/v1/notifications/unread-count", headers=h_a)
        assert count_a_self.json()["unread_count"] == 2

        # 6. Recipient Isolation & Ownership Security
        # User B cannot mark User A's notification as read
        cross_read = await client.patch(f"/api/v1/notifications/{notif_id}/read", headers=h_b)
        assert cross_read.status_code == 403

        # User B cannot delete User A's notification
        cross_delete = await client.delete(f"/api/v1/notifications/{notif_id}", headers=h_b)
        assert cross_delete.status_code == 403

        # 7. Mark as Read Transition
        mark_res = await client.patch(f"/api/v1/notifications/{notif_id}/read", headers=h_a)
        assert mark_res.status_code == 200
        assert mark_res.json()["read"] is True
        assert mark_res.json()["read_at"] is not None

        # Unread count should drop to 1
        count_a4 = await client.get("/api/v1/notifications/unread-count", headers=h_a)
        assert count_a4.json()["unread_count"] == 1

        # 8. Mark All Read
        all_read_res = await client.post("/api/v1/notifications/mark-all-read", headers=h_a)
        assert all_read_res.status_code == 200
        assert all_read_res.json()["unread_count"] == 0

        # Verify unread count is 0
        count_a5 = await client.get("/api/v1/notifications/unread-count", headers=h_a)
        assert count_a5.json()["unread_count"] == 0

        # 9. Dismiss / Delete Notification
        del_res = await client.delete(f"/api/v1/notifications/{notif_id}", headers=h_a)
        assert del_res.status_code == 200

        # Confirm total notifications decreased
        list_a_after = await client.get("/api/v1/notifications", headers=h_a)
        assert list_a_after.json()["total"] == 1
