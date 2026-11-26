"""
ZENOVA Phase 1.5 — Server-Side Blocking Hardening Test Suite.
Validates cross-subsystem blocking enforcement across Social Posts, Comments,
Likes, Connect Direct Messaging, Conversations, and Contact Discovery.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
import pytest
from bson import ObjectId
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database.client import connect_to_database, get_database, close_database_connection
from app.core.security import create_access_token, get_password_hash
from app.core.rate_limit import (
    auth_rate_limiter,
    social_post_rate_limiter,
    comment_rate_limiter,
    report_rate_limiter,
    search_rate_limiter,
)


@pytest.fixture(autouse=True)
async def init_phase1_5_test_db():
    await connect_to_database()
    # Clear rate limiters for deterministic test runs
    auth_rate_limiter.requests.clear()
    social_post_rate_limiter.requests.clear()
    comment_rate_limiter.requests.clear()
    report_rate_limiter.requests.clear()
    search_rate_limiter.requests.clear()
    yield


@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client


@pytest.fixture
async def setup_users():
    db = get_database()
    suffix = uuid.uuid4().hex[:6]

    # User A (Actor)
    u_a_id = ObjectId()
    u_a_data = {
        "_id": u_a_id,
        "email": f"alice_{suffix}@zenova.test",
        "username": f"alice_{suffix}",
        "full_name": f"Alice Test {suffix}",
        "hashed_password": get_password_hash("Password123!"),
        "is_active": True,
        "phone_verified": True,
        "phone_number": f"+9198111{suffix[:5]}",
        "blocked_users": [],
        "created_at": datetime.now(timezone.utc)
    }
    await db.users.insert_one(u_a_data)
    token_a = create_access_token(data={"sub": str(u_a_id), "email": u_a_data["email"], "type": "access"})

    # User B (Target)
    u_b_id = ObjectId()
    u_b_data = {
        "_id": u_b_id,
        "email": f"bob_{suffix}@zenova.test",
        "username": f"bob_{suffix}",
        "full_name": f"Bob Test {suffix}",
        "hashed_password": get_password_hash("Password123!"),
        "is_active": True,
        "phone_verified": True,
        "phone_number": f"+9198222{suffix[:5]}",
        "blocked_users": [],
        "created_at": datetime.now(timezone.utc)
    }
    await db.users.insert_one(u_b_data)
    token_b = create_access_token(data={"sub": str(u_b_id), "email": u_b_data["email"], "type": "access"})

    # User C (Unrelated control user)
    u_c_id = ObjectId()
    u_c_data = {
        "_id": u_c_id,
        "email": f"charlie_{suffix}@zenova.test",
        "username": f"charlie_{suffix}",
        "full_name": f"Charlie Test {suffix}",
        "hashed_password": get_password_hash("Password123!"),
        "is_active": True,
        "phone_verified": True,
        "phone_number": f"+9198333{suffix[:5]}",
        "blocked_users": [],
        "created_at": datetime.now(timezone.utc)
    }
    await db.users.insert_one(u_c_data)
    token_c = create_access_token(data={"sub": str(u_c_id), "email": u_c_data["email"], "type": "access"})

    users = {
        "a": {"id": str(u_a_id), "token": token_a, "headers": {"Authorization": f"Bearer {token_a}"}, "username": u_a_data["username"]},
        "b": {"id": str(u_b_id), "token": token_b, "headers": {"Authorization": f"Bearer {token_b}"}, "username": u_b_data["username"]},
        "c": {"id": str(u_c_id), "token": token_c, "headers": {"Authorization": f"Bearer {token_c}"}, "username": u_c_data["username"]},
    }

    yield users

    # Cleanup test data
    if db is not None:
        await db.users.delete_many({"_id": {"$in": [u_a_id, u_b_id, u_c_id]}})
        await db.posts.delete_many({"author_id": {"$in": [str(u_a_id), str(u_b_id), str(u_c_id)]}})
        await db.post_comments.delete_many({"author_id": {"$in": [str(u_a_id), str(u_b_id), str(u_c_id)]}})
        await db.chat_rooms.delete_many({"participants": {"$in": [str(u_a_id), str(u_b_id), str(u_c_id)]}})
        await db.chat_messages.delete_many({"sender_id": {"$in": [str(u_a_id), str(u_b_id), str(u_c_id)]}})
        await db.follows.delete_many({"$or": [
            {"follower_id": {"$in": [str(u_a_id), str(u_b_id), str(u_c_id)]}},
            {"following_id": {"$in": [str(u_a_id), str(u_b_id), str(u_c_id)]}}
        ]})


@pytest.mark.asyncio
async def test_complete_blocking_hardening_lifecycle(async_client, setup_users):
    u = setup_users
    a = u["a"]
    b = u["b"]
    c = u["c"]
    db = get_database()

    # -------------------------------------------------------------
    # 1. Pre-block baseline: create pre-existing conversation and posts
    # -------------------------------------------------------------
    # User A creates a post
    post_a_res = await async_client.post(
        "/api/v1/social/posts",
        json={"content": "Alice Sovereign Post Before Block"},
        headers=a["headers"]
    )
    assert post_a_res.status_code == 201
    post_a_id = post_a_res.json()["id"]

    # User B creates a post
    post_b_res = await async_client.post(
        "/api/v1/social/posts",
        json={"content": "Bob Public Post Before Block"},
        headers=b["headers"]
    )
    assert post_b_res.status_code == 201
    post_b_id = post_b_res.json()["id"]

    # Pre-block: User B can comment on User A's post
    comm_pre = await async_client.post(
        f"/api/v1/social/posts/{post_a_id}/comments",
        json={"content": "Bob initial comment"},
        headers=b["headers"]
    )
    assert comm_pre.status_code == 201

    # Pre-block: User A and User B create a direct conversation
    conv_res = await async_client.post(
        "/api/v1/chat/conversations",
        json={"recipient_id": b["id"]},
        headers=a["headers"]
    )
    assert conv_res.status_code == 200
    conv_id = conv_res.json()["id"]

    # Pre-block: User B sends message to User A in the direct conversation
    msg_pre = await async_client.post(
        f"/api/v1/chat/conversations/{conv_id}/messages",
        json={"text": "Hello Alice, working together!"},
        headers=b["headers"]
    )
    assert msg_pre.status_code == 201

    # -------------------------------------------------------------
    # 2. Block Action: User A blocks User B
    # -------------------------------------------------------------
    block_res = await async_client.post(
        f"/api/v1/platform/users/{b['id']}/block",
        headers=a["headers"]
    )
    assert block_res.status_code == 200
    assert block_res.json()["status"] == "blocked"
    assert block_res.json()["target_user_id"] == b["id"]

    # Verify Database state
    user_a_doc = await db.users.find_one({"_id": ObjectId(a["id"])})
    assert b["id"] in user_a_doc.get("blocked_users", [])

    # -------------------------------------------------------------
    # 3. Duplicate Block Handling (Idempotence)
    # -------------------------------------------------------------
    dup_block_res = await async_client.post(
        f"/api/v1/platform/users/{b['id']}/block",
        headers=a["headers"]
    )
    assert dup_block_res.status_code == 200
    user_a_doc2 = await db.users.find_one({"_id": ObjectId(a["id"])})
    assert user_a_doc2.get("blocked_users", []).count(b["id"]) == 1

    # -------------------------------------------------------------
    # 4. Comments Blocking (Bidirectional Server-Side Enforcement)
    # -------------------------------------------------------------
    # User B attempts to comment on User A's post -> MUST return 404 (Not Found, zero info leak)
    b_comment_attempt = await async_client.post(
        f"/api/v1/social/posts/{post_a_id}/comments",
        json={"content": "Blocked attempt to comment by Bob"},
        headers=b["headers"]
    )
    assert b_comment_attempt.status_code == 404

    # User A attempts to comment on User B's post -> MUST return 404
    a_comment_attempt = await async_client.post(
        f"/api/v1/social/posts/{post_b_id}/comments",
        json={"content": "Alice attempt to comment on blocked Bob post"},
        headers=a["headers"]
    )
    assert a_comment_attempt.status_code == 404

    # User B attempts to like User A's post -> MUST return 404
    b_like_attempt = await async_client.post(
        f"/api/v1/social/posts/{post_a_id}/like",
        headers=b["headers"]
    )
    assert b_like_attempt.status_code == 404

    # -------------------------------------------------------------
    # 5. Connect Chat Blocking: New Conversation Creation
    # -------------------------------------------------------------
    # User B attempts to create conversation with User A -> 403 Forbidden
    b_create_conv = await async_client.post(
        "/api/v1/chat/conversations",
        json={"recipient_id": a["id"]},
        headers=b["headers"]
    )
    assert b_create_conv.status_code == 403

    # User A attempts to create conversation with User B -> 403 Forbidden
    a_create_conv = await async_client.post(
        "/api/v1/chat/conversations",
        json={"recipient_id": b["id"]},
        headers=a["headers"]
    )
    assert a_create_conv.status_code == 403

    # -------------------------------------------------------------
    # 6. Existing Conversations After Blocking
    # -------------------------------------------------------------
    # User B attempts to send message in pre-existing conversation -> 403 Forbidden
    b_send_msg = await async_client.post(
        f"/api/v1/chat/conversations/{conv_id}/messages",
        json={"text": "Bob trying to bypass block in old chat"},
        headers=b["headers"]
    )
    assert b_send_msg.status_code == 403

    # User A attempts to send message in pre-existing conversation -> 403 Forbidden
    a_send_msg = await async_client.post(
        f"/api/v1/chat/conversations/{conv_id}/messages",
        json={"text": "Alice trying to message blocked user in old chat"},
        headers=a["headers"]
    )
    assert a_send_msg.status_code == 403

    # User B attempts to get conversation messages -> 404 Not Found
    b_get_msgs = await async_client.get(
        f"/api/v1/chat/conversations/{conv_id}/messages",
        headers=b["headers"]
    )
    assert b_get_msgs.status_code == 404

    # User A lists conversations -> direct conversation with B must be excluded
    a_list_convs = await async_client.get(
        "/api/v1/chat/conversations",
        headers=a["headers"]
    )
    assert a_list_convs.status_code == 200
    assert not any(c_item["id"] == conv_id for c_item in a_list_convs.json())

    # -------------------------------------------------------------
    # 7. Contact Discovery Isolation
    # -------------------------------------------------------------
    # User B searches for Alice -> Alice must be excluded
    b_search = await async_client.get(
        f"/api/v1/chat/users/search?q={a['username'][:5]}",
        headers=b["headers"]
    )
    assert b_search.status_code == 200
    assert not any(u_item["id"] == a["id"] for u_item in b_search.json())

    # User A searches for Bob -> Bob must be excluded
    a_search = await async_client.get(
        f"/api/v1/chat/users/search?q={b['username'][:5]}",
        headers=a["headers"]
    )
    assert a_search.status_code == 200
    assert not any(u_item["id"] == b["id"] for u_item in a_search.json())

    # -------------------------------------------------------------
    # 8. Unrelated User (Charlie) Sanity Check
    # -------------------------------------------------------------
    # Charlie (User C) can comment on Alice's post -> 201 Created
    c_comment = await async_client.post(
        f"/api/v1/social/posts/{post_a_id}/comments",
        json={"content": "Charlie public positive comment"},
        headers=c["headers"]
    )
    assert c_comment.status_code == 201

    # Charlie can message Alice -> 200 OK
    c_conv = await async_client.post(
        "/api/v1/chat/conversations",
        json={"recipient_id": a["id"]},
        headers=c["headers"]
    )
    assert c_conv.status_code == 200

    # -------------------------------------------------------------
    # 9. Unblock Action & Recovery
    # -------------------------------------------------------------
    # User A unblocks User B
    unblock_res = await async_client.delete(
        f"/api/v1/platform/users/{b['id']}/block",
        headers=a["headers"]
    )
    assert unblock_res.status_code == 200
    assert unblock_res.json()["status"] == "unblocked"

    # Verify DB state: b["id"] no longer in blocked_users
    user_a_doc_unblocked = await db.users.find_one({"_id": ObjectId(a["id"])})
    assert b["id"] not in user_a_doc_unblocked.get("blocked_users", [])

    # Now User B can comment on Alice's post again -> 201 Created
    b_comment_after = await async_client.post(
        f"/api/v1/social/posts/{post_a_id}/comments",
        json={"content": "Bob commenting after being unblocked"},
        headers=b["headers"]
    )
    assert b_comment_after.status_code == 201

    # Now User B can send messages in the conversation again -> 201 Created
    b_send_after = await async_client.post(
        f"/api/v1/chat/conversations/{conv_id}/messages",
        json={"text": "Bob messaging after being unblocked"},
        headers=b["headers"]
    )
    assert b_send_after.status_code == 201
