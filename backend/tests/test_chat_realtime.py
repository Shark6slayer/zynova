import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database.client import connect_to_database, close_database_connection, get_database
from app.core.rate_limit import auth_rate_limiter, chat_rate_limiter
from app.core.ws_manager import chat_manager

@pytest.fixture(autouse=True)
async def init_chat_db():
    await connect_to_database()
    auth_rate_limiter.requests.clear()
    chat_rate_limiter.requests.clear()
    yield
    db = get_database()
    if db is not None:
        await db.users.delete_many({"email": {"$in": ["chat_user1@superai.in", "chat_user2@superai.in", "intruder@superai.in"]}})
        await db.chat_rooms.delete_many({})
        await db.chat_messages.delete_many({})
    await close_database_connection()

@pytest.mark.asyncio
async def test_complete_realtime_chat_lifecycle():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Register User 1 & User 2
        u1_res = await ac.post("/api/v1/auth/register", json={
            "email": "chat_user1@superai.in",
            "username": "user1_chat",
            "full_name": "Arun Kumar",
            "password": "Password123!"
        })
        assert u1_res.status_code == 201
        u1_id = u1_res.json()["id"]

        u2_res = await ac.post("/api/v1/auth/register", json={
            "email": "chat_user2@superai.in",
            "username": "user2_chat",
            "full_name": "Priya Sharma",
            "password": "Password123!"
        })
        assert u2_res.status_code == 201
        u2_id = u2_res.json()["id"]

        # Intruder User
        int_res = await ac.post("/api/v1/auth/register", json={
            "email": "intruder@superai.in",
            "username": "intruder_user",
            "full_name": "Intruder User",
            "password": "Password123!"
        })
        assert int_res.status_code == 201
        int_id = int_res.json()["id"]

        # 2. Login both users
        login1 = await ac.post("/api/v1/auth/login", json={"email": "chat_user1@superai.in", "password": "Password123!"})
        tok1 = login1.json()["access_token"]
        h1 = {"Authorization": f"Bearer {tok1}"}

        login2 = await ac.post("/api/v1/auth/login", json={"email": "chat_user2@superai.in", "password": "Password123!"})
        tok2 = login2.json()["access_token"]
        h2 = {"Authorization": f"Bearer {tok2}"}

        login_int = await ac.post("/api/v1/auth/login", json={"email": "intruder@superai.in", "password": "Password123!"})
        tok_int = login_int.json()["access_token"]
        h_int = {"Authorization": f"Bearer {tok_int}"}

        # 3. User 1 searches for User 2
        search_res = await ac.get("/api/v1/chat/users/search?q=Priya", headers=h1)
        assert search_res.status_code == 200
        search_users = search_res.json()
        assert len(search_users) >= 1
        assert any(u["username"] == "user2_chat" for u in search_users)

        # 4. User 1 creates 1-to-1 conversation with User 2
        conv_res = await ac.post("/api/v1/chat/conversations", json={"recipient_id": u2_id}, headers=h1)
        assert conv_res.status_code == 200
        conv_data = conv_res.json()
        conv_id = conv_data["id"]
        assert u1_id in conv_data["participants"]
        assert u2_id in conv_data["participants"]

        # Duplicate conversation request returns the existing conversation
        conv_dup = await ac.post("/api/v1/chat/conversations", json={"recipient_id": u2_id}, headers=h1)
        assert conv_dup.status_code == 200
        assert conv_dup.json()["id"] == conv_id

        # 5. User 1 sends message to User 2
        msg1_res = await ac.post(f"/api/v1/chat/conversations/{conv_id}/messages", json={
            "text": "Hello Priya! Welcome to SUPER_AI real-time chat."
        }, headers=h1)
        assert msg1_res.status_code == 201
        msg1_data = msg1_res.json()
        assert msg1_data["sender_id"] == u1_id
        assert msg1_data["text"] == "Hello Priya! Welcome to SUPER_AI real-time chat."
        msg1_id = msg1_data["id"]

        # 6. User 2 lists conversations: should see unread count = 1
        u2_convs = await ac.get("/api/v1/chat/conversations", headers=h2)
        assert u2_convs.status_code == 200
        u2_room = next(r for r in u2_convs.json() if r["id"] == conv_id)
        assert u2_room["unread_count"] == 1
        assert u2_room["last_message"]["text"] == "Hello Priya! Welcome to SUPER_AI real-time chat."

        # 7. User 2 checks total unread count
        u2_unread = await ac.get("/api/v1/chat/unread-count", headers=h2)
        assert u2_unread.status_code == 200
        assert u2_unread.json()["unread_count"] == 1

        # 8. User 2 retrieves messages history
        hist_res = await ac.get(f"/api/v1/chat/conversations/{conv_id}/messages?limit=20", headers=h2)
        assert hist_res.status_code == 200
        history = hist_res.json()
        assert len(history) == 1
        assert history[0]["id"] == msg1_id

        # 9. User 2 marks conversation as read
        read_res = await ac.post(f"/api/v1/chat/conversations/{conv_id}/read", headers=h2)
        assert read_res.status_code == 200

        # Unread count should now be 0 for User 2
        u2_unread_after = await ac.get("/api/v1/chat/unread-count", headers=h2)
        assert u2_unread_after.json()["unread_count"] == 0

        # 10. User 1 edits their own message
        edit_res = await ac.patch(f"/api/v1/chat/messages/{msg1_id}", json={
            "text": "Hello Priya! (Edited: Welcome to Indic Super App)"
        }, headers=h1)
        assert edit_res.status_code == 200
        assert edit_res.json()["is_edited"] is True
        assert edit_res.json()["text"] == "Hello Priya! (Edited: Welcome to Indic Super App)"

        # User 2 CANNOT edit User 1's message (Forbidden)
        illegal_edit = await ac.patch(f"/api/v1/chat/messages/{msg1_id}", json={
            "text": "Malicious edit attempt"
        }, headers=h2)
        assert illegal_edit.status_code == 403

        # 11. Intruder user CANNOT view messages of User 1 & 2's conversation
        intruder_read = await ac.get(f"/api/v1/chat/conversations/{conv_id}/messages", headers=h_int)
        assert intruder_read.status_code == 404

        # Intruder CANNOT send message into conversation
        intruder_send = await ac.post(f"/api/v1/chat/conversations/{conv_id}/messages", json={
            "text": "Intruder injection"
        }, headers=h_int)
        assert intruder_send.status_code == 404

        # 12. User 1 deletes their own message (Soft delete)
        del_res = await ac.delete(f"/api/v1/chat/messages/{msg1_id}", headers=h1)
        assert del_res.status_code == 200
        assert del_res.json()["is_deleted"] is True
        assert del_res.json()["text"] == "This message was deleted."

        # Verify in history that text is replaced and marked deleted
        verify_hist = await ac.get(f"/api/v1/chat/conversations/{conv_id}/messages", headers=h2)
        assert verify_hist.json()[0]["is_deleted"] is True
        assert verify_hist.json()[0]["text"] == "This message was deleted."
