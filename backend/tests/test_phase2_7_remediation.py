import asyncio
from datetime import datetime, timezone
import pytest
from httpx import AsyncClient, ASGITransport
from bson import ObjectId

from app.main import app
from app.database.client import connect_to_database, close_database_connection, get_database
from app.core.security import create_access_token, get_password_hash


@pytest.fixture(autouse=True)
async def setup_db():
    await connect_to_database()
    yield
    await close_database_connection()


async def _seed_user(db, email, username):
    await db.users.delete_many({"email": email})
    await db.users.delete_many({"username": username})
    res = await db.users.insert_one({
        "email": email,
        "username": username,
        "zen_id": username,
        "full_name": username,
        "hashed_password": get_password_hash("TestPass#2026"),
        "is_active": True,
        "is_verified": True,
        "account_status": "active",
        "created_at": datetime.now(timezone.utc),
    })
    uid = str(res.inserted_id)
    tok = create_access_token({"sub": uid, "email": email, "type": "access"})
    return uid, tok


@pytest.mark.asyncio
async def test_zenosocial_three_message_limit_and_concurrency():
    db = get_database()
    a_id, a_tok = await _seed_user(db, "p27_alice@zenova.test", "p27_alice")
    b_id, b_tok = await _seed_user(db, "p27_bob@zenova.test", "p27_bob")
    c_id, c_tok = await _seed_user(db, "p27_charlie@zenova.test", "p27_charlie")
    await db.follows.delete_many({"$or": [{"follower_id": a_id}, {"follower_id": b_id}, {"follower_id": c_id}]})
    await db.social_conversations.delete_many({"participant_ids": {"$in": [a_id, b_id, c_id]}})
    await db.social_messages.delete_many({"sender_id": {"$in": [a_id, b_id, c_id]}})

    h_a = {"Authorization": f"Bearer {a_tok}"}
    h_b = {"Authorization": f"Bearer {b_tok}"}
    h_c = {"Authorization": f"Bearer {c_tok}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1-3 allowed, 4th rejected for non-mutual Alice -> Bob
        for i in range(3):
            r = await ac.post("/api/v1/social/messages/send", headers=h_a, json={"recipient_zen_id": "p27_bob", "text": f"Msg {i+1}"})
            assert r.status_code == 201
        r4 = await ac.post("/api/v1/social/messages/send", headers=h_a, json={"recipient_zen_id": "p27_bob", "text": "Msg 4"})
        assert r4.status_code == 403

        # Share-content endpoint also enforces the cap
        r_share = await ac.post("/api/v1/social/messages/share-content", headers=h_a, json={
            "recipient_zen_ids": ["p27_bob"], "content_type": "post", "content_id": "p1", "message": "Bypass?"
        })
        assert r_share.status_code == 403

        # Recipient follows sender -> mutual -> unlimited messaging unlocked
        await db.follows.insert_one({"follower_id": a_id, "following_id": b_id, "created_at": datetime.now(timezone.utc)})
        await db.follows.insert_one({"follower_id": b_id, "following_id": a_id, "created_at": datetime.now(timezone.utc)})
        r5 = await ac.post("/api/v1/social/messages/send", headers=h_a, json={"recipient_zen_id": "p27_bob", "text": "Mutual Msg 5"})
        assert r5.status_code == 201

        # Concurrent burst (6 parallel requests) between non-mutual Charlie -> Bob: at most 3 succeed
        burst = await asyncio.gather(*[
            ac.post("/api/v1/social/messages/send", headers=h_c, json={"recipient_zen_id": "p27_bob", "text": f"Burst {i}"})
            for i in range(6)
        ])
        ok_count = sum(1 for r in burst if r.status_code == 201)
        rejected_count = sum(1 for r in burst if r.status_code == 403)
        assert ok_count == 3
        assert rejected_count == 3


@pytest.mark.asyncio
async def test_deleted_user_token_returns_401():
    db = get_database()
    u_id, u_tok = await _seed_user(db, "p27_deleted@zenova.test", "p27_deleted")
    headers = {"Authorization": f"Bearer {u_tok}"}

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        r_ok = await ac.get("/api/v1/users/me", headers=headers)
        assert r_ok.status_code == 200

        # Simulate permanent user deletion
        await db.users.delete_one({"_id": ObjectId(u_id)})
        r_del = await ac.get("/api/v1/users/me", headers=headers)
        assert r_del.status_code == 401
