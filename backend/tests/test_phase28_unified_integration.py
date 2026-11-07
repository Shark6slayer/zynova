import pytest
import uuid
from httpx import AsyncClient, ASGITransport
from datetime import datetime, timezone
from bson import ObjectId

from app.main import app
from app.database.client import connect_to_database, get_database
from app.core.security import create_access_token, get_password_hash
from app.core.rate_limit import search_rate_limiter

@pytest.fixture(autouse=True)
async def init_phase28_db():
    await connect_to_database()
    search_rate_limiter.requests.clear()
    yield
    search_rate_limiter.requests.clear()

@pytest.fixture
async def async_client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client

@pytest.fixture
async def setup_test_users():
    db = get_database()
    suffix = uuid.uuid4().hex[:8]
    
    # User 1: Primary user
    u1_id = ObjectId()
    u1_data = {
        "_id": u1_id,
        "email": f"primary_{suffix}@zynova.net",
        "username": f"primary_{suffix}",
        "full_name": "Primary User",
        "hashed_password": get_password_hash("Password123!"),
        "is_active": True,
        "bio": "Lead architect on Zynova",
        "avatar_url": "https://cdn.zynova.net/avatars/u1.jpg",
        "created_at": datetime.now(timezone.utc)
    }
    await db.users.insert_one(u1_data)
    token1 = create_access_token(data={"sub": str(u1_id), "email": u1_data["email"]})

    # User 2: Peer user
    u2_id = ObjectId()
    u2_data = {
        "_id": u2_id,
        "email": f"peer_{suffix}@zynova.net",
        "username": f"peer_{suffix}",
        "full_name": "Peer User",
        "hashed_password": get_password_hash("Password123!"),
        "is_active": True,
        "bio": "Content creator on Zynova",
        "avatar_url": "https://cdn.zynova.net/avatars/u2.jpg",
        "created_at": datetime.now(timezone.utc)
    }
    await db.users.insert_one(u2_data)
    token2 = create_access_token(data={"sub": str(u2_id), "email": u2_data["email"]})

    yield {
        "u1_id": str(u1_id),
        "u1_username": u1_data["username"],
        "token1": token1,
        "u2_id": str(u2_id),
        "u2_username": u2_data["username"],
        "token2": token2,
        "suffix": suffix
    }

    # Cleanup
    if db is not None:
        await db.users.delete_many({"_id": {"$in": [u1_id, u2_id]}})
        await db.posts.delete_many({"author_id": {"$in": [str(u1_id), str(u2_id)]}})
        await db.videos.delete_many({"owner_id": {"$in": [str(u1_id), str(u2_id)]}})
        await db.creator_channels.delete_many({"owner_id": {"$in": [str(u1_id), str(u2_id)]}})
        await db.search_history.delete_many({"user_id": {"$in": [str(u1_id), str(u2_id)]}})
        await db.notification_preferences.delete_many({"user_id": {"$in": [str(u1_id), str(u2_id)]}})

# 1. Unified Identity Across Social, Connect & Video
@pytest.mark.asyncio
async def test_unified_identity_across_all_three_platforms(async_client, setup_test_users):
    u = setup_test_users
    headers1 = {"Authorization": f"Bearer {u['token1']}"}

    # Check Unified Profile
    res = await async_client.get("/api/v1/platform/me/profile", headers=headers1)
    assert res.status_code == 200
    profile = res.json()
    assert profile["id"] == u["u1_id"]
    assert profile["username"] == u["u1_username"]
    assert "social_profile" in profile
    assert "connect_profile" in profile
    assert "video_channel" in profile

    # Update Social Sub-profile
    patch_social = await async_client.patch(
        "/api/v1/platform/me/social",
        json={"is_private": True, "pronouns": "they/them"},
        headers=headers1
    )
    assert patch_social.status_code == 200

    # Update Connect Sub-profile
    patch_connect = await async_client.patch(
        "/api/v1/platform/me/connect",
        json={"display_name": "Primary (Connect)", "about_text": "Always ready to chat"},
        headers=headers1
    )
    assert patch_connect.status_code == 200

    # Re-fetch Unified Profile to verify atomicity
    verify_res = await async_client.get("/api/v1/platform/me/profile", headers=headers1)
    updated_profile = verify_res.json()
    assert updated_profile["social_profile"]["is_private"] is True
    assert updated_profile["connect_profile"]["display_name"] == "Primary (Connect)"

# 2. Unified Global Search (People, Posts, Videos, Shorts, Channels, Communities)
@pytest.mark.asyncio
async def test_unified_global_search(async_client, setup_test_users):
    u = setup_test_users
    db = get_database()
    headers1 = {"Authorization": f"Bearer {u['token1']}"}

    # Seed a public post
    await db.posts.insert_one({
        "author_id": u["u2_id"],
        "author_username": u["u2_username"],
        "author_full_name": "Peer Creator",
        "content": f"Exploring quantum computing in {u['suffix']} today!",
        "media_type": "text",
        "created_at": datetime.now(timezone.utc)
    })

    # Seed a public video
    await db.videos.insert_one({
        "owner_id": u["u2_id"],
        "channel_name": "Tech Channel",
        "title": f"Quantum Computing Deep Dive {u['suffix']}",
        "description": "Full tutorial on qubits",
        "category": "Technology",
        "is_short": False,
        "visibility": "public",
        "views_count": 42,
        "created_at": datetime.now(timezone.utc)
    })

    # Global search query
    res = await async_client.get(f"/api/v1/search?q=Quantum&type=all", headers=headers1)
    assert res.status_code == 200
    data = res.json()
    assert data["total_count"] >= 2
    types_found = {r["result_type"] for r in data["results"]}
    assert "post" in types_found
    assert "video" in types_found

    # Test search history persistence
    hist_res = await async_client.get("/api/v1/search/history", headers=headers1)
    assert hist_res.status_code == 200
    history = hist_res.json()
    assert len(history) >= 1
    assert history[0]["query"] == "Quantum"

    # Test deleting history item
    item_id = history[0]["id"]
    del_res = await async_client.delete(f"/api/v1/search/history/{item_id}", headers=headers1)
    assert del_res.status_code == 200

# 3. Privacy & Blocking Enforcement in Search and Sharing
@pytest.mark.asyncio
async def test_search_and_share_blocking_isolation(async_client, setup_test_users):
    u = setup_test_users
    headers1 = {"Authorization": f"Bearer {u['token1']}"}
    headers2 = {"Authorization": f"Bearer {u['token2']}"}

    # User 1 blocks User 2
    block_res = await async_client.post(f"/api/v1/platform/users/{u['u2_id']}/block", headers=headers1)
    assert block_res.status_code == 200

    # User 1 searches for User 2 -> Must NOT appear
    search_res = await async_client.get(f"/api/v1/search?q={u['u2_username']}&type=people", headers=headers1)
    assert search_res.status_code == 200
    results = search_res.json()["results"]
    assert not any(r["id"] == u["u2_id"] for r in results)

    # Share link resolution for User 2 profile accessed by User 1 -> 403 Forbidden
    share_res = await async_client.get(f"/api/v1/platform/share/profile/{u['u2_id']}", headers=headers1)
    assert share_res.status_code == 403

# 4. Cross-Platform Content Sharing & Deep Links
@pytest.mark.asyncio
async def test_cross_platform_sharing_and_deep_links(async_client, setup_test_users):
    u = setup_test_users
    db = get_database()

    # Seed a public video
    vid_id = ObjectId()
    await db.videos.insert_one({
        "_id": vid_id,
        "owner_id": u["u1_id"],
        "channel_name": "Studio Channel",
        "title": "Zynova Video Masterclass",
        "description": "Learn the new video platform",
        "is_short": False,
        "visibility": "public",
        "created_at": datetime.now(timezone.utc)
    })

    # Resolve share metadata
    res = await async_client.get(f"/api/v1/platform/share/video/{str(vid_id)}")
    assert res.status_code == 200
    data = res.json()
    assert data["content_type"] == "video"
    assert data["title"] == "Zynova Video Masterclass"
    assert data["deep_link"] == f"/videos/{str(vid_id)}"
    assert data["is_public"] is True

# 5. Unified Notification Preferences & Category Filtering
@pytest.mark.asyncio
async def test_unified_notification_preferences(async_client, setup_test_users):
    u = setup_test_users
    headers1 = {"Authorization": f"Bearer {u['token1']}"}

    # Fetch default preferences
    res = await async_client.get("/api/v1/notifications/preferences", headers=headers1)
    assert res.status_code == 200
    prefs = res.json()
    assert prefs["social_likes"] is True
    assert prefs["video_subscriptions"] is True

    # Update preferences
    patch_res = await async_client.patch(
        "/api/v1/notifications/preferences",
        json={"video_subscriptions": False, "preview_privacy": "sender_only"},
        headers=headers1
    )
    assert patch_res.status_code == 200
    updated = patch_res.json()
    assert updated["video_subscriptions"] is False
    assert updated["preview_privacy"] == "sender_only"

# 6. Cascade Account Deactivation & Deletion
@pytest.mark.asyncio
async def test_account_deactivation_and_cascade_policy(async_client, setup_test_users):
    u = setup_test_users
    db = get_database()
    headers2 = {"Authorization": f"Bearer {u['token2']}"}

    # Deactivate User 2
    deact_res = await async_client.post(
        "/api/v1/users/me/deactivate",
        json={"password": "Password123!"},
        headers=headers2
    )
    assert deact_res.status_code == 200
    assert deact_res.json()["status"] == "deactivated"

    # Verify User 2 is marked inactive
    user2_doc = await db.users.find_one({"_id": ObjectId(u["u2_id"])})
    assert user2_doc["is_active"] is False
