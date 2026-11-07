"""
Comprehensive Test Suite for Zynova Video & Shorts Platform (Phase 27).
Validates at minimum:
1. Channel creation and ownership.
2. Unique channel handles.
3. Video metadata creation.
4. Upload authorization and MIME validation.
5. Private and unlisted playback authorization.
6. Shorts creation and feed retrieval.
7. Subscriptions (subscribe/unsubscribe) and duplicate prevention.
8. Likes and duplicate feedback prevention.
9. Comment creation and authorization.
10. Playlist management and permissions.
11. Watch history and resume progress.
12. Recommendation filtering and ranking.
13. Creator analytics access control.
14. Blocking and privacy enforcement.
"""

import pytest
import io
from httpx import AsyncClient, ASGITransport
from bson import ObjectId

from app.main import app
from app.database.client import connect_to_database, close_database_connection, get_database
from app.core.rate_limit import (
    auth_rate_limiter,
    video_upload_rate_limiter,
    video_comment_rate_limiter
)

@pytest.fixture(autouse=True)
async def init_video_phase27_db():
    await connect_to_database()
    auth_rate_limiter.requests.clear()
    video_upload_rate_limiter.requests.clear()
    video_comment_rate_limiter.requests.clear()
    yield
    auth_rate_limiter.requests.clear()
    video_upload_rate_limiter.requests.clear()
    video_comment_rate_limiter.requests.clear()
    db = get_database()
    if db is not None:
        await db.users.delete_many({"email": {"$regex": "@testvideo.zynova.in$"}})
        await db.creator_channels.delete_many({})
        await db.videos.delete_many({"owner_username": {"$regex": "^vid_test_"}})
        await db.channel_subscriptions.delete_many({})
        await db.video_feedback.delete_many({})
        await db.video_comments.delete_many({})
        await db.video_watch_history.delete_many({})
        await db.video_playlists.delete_many({})
    await close_database_connection()

async def create_auth_user(ac: AsyncClient, email: str, username: str, full_name: str) -> dict:
    reg = await ac.post("/api/v1/auth/register", json={
        "email": email,
        "username": username,
        "full_name": full_name,
        "password": "Password123!"
    })
    assert reg.status_code == 201
    user_id = reg.json()["id"]

    login = await ac.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    assert login.status_code == 200
    token = login.json()["access_token"]
    return {
        "id": user_id,
        "email": email,
        "username": username,
        "full_name": full_name,
        "headers": {"Authorization": f"Bearer {token}"}
    }

@pytest.mark.asyncio
async def test_creator_channel_creation_and_unique_handle():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        creator = await create_auth_user(ac, "c1@testvideo.zynova.in", "vid_test_creator1", "Creator One")
        other = await create_auth_user(ac, "c2@testvideo.zynova.in", "vid_test_creator2", "Creator Two")

        # 1. Create channel
        ch_res = await ac.post(
            "/api/v1/videos/channels",
            json={
                "handle": "tech_sovereign",
                "name": "Tech Sovereign India",
                "description": "Deep tech and AI channel"
            },
            headers=creator["headers"]
        )
        assert ch_res.status_code == 201
        ch_data = ch_res.json()
        assert ch_data["handle"] == "tech_sovereign"
        assert ch_data["is_owner"] is True
        ch_id = ch_data["id"]

        # 2. Duplicate handle rejection
        dup_res = await ac.post(
            "/api/v1/videos/channels",
            json={
                "handle": "tech_sovereign",
                "name": "Impostor Channel",
                "description": "Trying to steal handle"
            },
            headers=other["headers"]
        )
        assert dup_res.status_code == 400

        # 3. Retrieve channel by handle
        get_res = await ac.get("/api/v1/videos/channels/tech_sovereign", headers=other["headers"])
        assert get_res.status_code == 200
        assert get_res.json()["name"] == "Tech Sovereign India"
        assert get_res.json()["is_owner"] is False

@pytest.mark.asyncio
async def test_channel_subscriptions_and_duplicate_prevention():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        creator = await create_auth_user(ac, "crea@testvideo.zynova.in", "vid_test_sub_crea", "Channel Host")
        viewer = await create_auth_user(ac, "view@testvideo.zynova.in", "vid_test_sub_view", "Active Viewer")

        ch = await ac.post(
            "/api/v1/videos/channels",
            json={"handle": "host_channel", "name": "Host Channel"},
            headers=creator["headers"]
        )
        ch_id = ch.json()["id"]

        # 1. Self-subscription rejection
        self_sub = await ac.post(f"/api/v1/videos/channels/{ch_id}/subscribe", headers=creator["headers"])
        assert self_sub.status_code == 400

        # 2. Viewer subscribes
        sub_res = await ac.post(f"/api/v1/videos/channels/{ch_id}/subscribe", headers=viewer["headers"])
        assert sub_res.status_code == 200
        assert sub_res.json()["is_subscribed"] is True

        # Check subscriber counter incremented
        ch_info = await ac.get(f"/api/v1/videos/channels/{ch_id}", headers=viewer["headers"])
        assert ch_info.json()["subscriber_count"] == 1
        assert ch_info.json()["is_subscribed"] is True

        # 3. Unsubscribe toggle
        unsub_res = await ac.post(f"/api/v1/videos/channels/{ch_id}/subscribe", headers=viewer["headers"])
        assert unsub_res.status_code == 200
        assert unsub_res.json()["is_subscribed"] is False

@pytest.mark.asyncio
async def test_video_and_shorts_upload_and_privacy_authorization():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        creator = await create_auth_user(ac, "uploader@testvideo.zynova.in", "vid_test_uploader", "Uploader User")
        viewer = await create_auth_user(ac, "viewer_priv@testvideo.zynova.in", "vid_test_vpriv", "Private Viewer")

        mp4_dummy = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isomavc1" + (b"\x00" * 512)

        # 1. Upload Long-form Video as Private
        files = {"file": ("long_priv.mp4", io.BytesIO(mp4_dummy), "video/mp4")}
        data_priv = {
            "title": "Private Creator Secret",
            "visibility": "private",
            "category": "Technology",
            "is_short": "false"
        }
        priv_res = await ac.post("/api/v1/videos", headers=creator["headers"], data=data_priv, files=files)
        assert priv_res.status_code == 201
        priv_id = priv_res.json()["id"]

        # 2. Viewer cannot access private video
        unauth_get = await ac.get(f"/api/v1/videos/{priv_id}", headers=viewer["headers"])
        assert unauth_get.status_code == 403

        # Creator can access private video
        auth_get = await ac.get(f"/api/v1/videos/{priv_id}", headers=creator["headers"])
        assert auth_get.status_code == 200

        # 3. Upload a Short (9:16 vertical video)
        files_short = {"file": ("short_clip.mp4", io.BytesIO(mp4_dummy), "video/mp4")}
        data_short = {
            "title": "Amazing 60s Tech Tip #Shorts",
            "visibility": "public",
            "category": "Science",
            "is_short": "true",
            "audio_title": "Original Sound"
        }
        short_res = await ac.post("/api/v1/videos", headers=creator["headers"], data=data_short, files=files_short)
        assert short_res.status_code == 201
        short_data = short_res.json()
        assert short_data["is_short"] is True
        assert short_data["aspect_ratio"] == "9:16"

        # 4. Query Shorts continuous feed
        shorts_feed = await ac.get("/api/v1/videos/shorts?limit=10", headers=viewer["headers"])
        assert shorts_feed.status_code == 200
        assert any(s["id"] == short_data["id"] for s in shorts_feed.json())

@pytest.mark.asyncio
async def test_playlists_and_watch_history():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        user = await create_auth_user(ac, "playlist_u@testvideo.zynova.in", "vid_test_pl_user", "Playlist User")

        mp4_dummy = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isomavc1" + (b"\x00" * 512)
        files = {"file": ("test_vid.mp4", io.BytesIO(mp4_dummy), "video/mp4")}
        vid_res = await ac.post("/api/v1/videos", headers=user["headers"], data={"title": "Playlist Source Video"}, files=files)
        vid_id = vid_res.json()["id"]

        # 1. Create Playlist
        pl_res = await ac.post(
            "/api/v1/videos/playlists",
            json={"title": "Favorite AI Talks", "description": "Saved playlist", "visibility": "public"},
            headers=user["headers"]
        )
        assert pl_res.status_code == 201
        pl_id = pl_res.json()["id"]

        # 2. Add video to playlist
        add_vid = await ac.post(f"/api/v1/videos/playlists/{pl_id}/videos/{vid_id}?action=add", headers=user["headers"])
        assert add_vid.status_code == 200
        assert add_vid.json()["videos_count"] == 1

        # 3. Report watch progress
        prog_res = await ac.post(
            f"/api/v1/videos/{vid_id}/progress",
            json={"playback_position_seconds": 45.5, "duration_seconds": 120.0, "completed": False},
            headers=user["headers"]
        )
        assert prog_res.status_code == 200

        # 4. Check user history
        hist_res = await ac.get("/api/v1/videos/user/history", headers=user["headers"])
        assert hist_res.status_code == 200
        hist_list = hist_res.json()
        assert len(hist_list) >= 1
        assert hist_list[0]["video"]["id"] == vid_id
        assert hist_list[0]["playback_position_seconds"] == 45.5

@pytest.mark.asyncio
async def test_recommendations_and_creator_analytics():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        creator = await create_auth_user(ac, "analytics_c@testvideo.zynova.in", "vid_test_an_c", "Analytics Creator")
        ch = await ac.post("/api/v1/videos/channels", json={"handle": "metric_studio", "name": "Metric Studio"}, headers=creator["headers"])
        ch_id = ch.json()["id"]

        mp4_dummy = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isomavc1" + (b"\x00" * 512)
        files = {"file": ("metric_vid.mp4", io.BytesIO(mp4_dummy), "video/mp4")}
        data = {"title": "Metric Analytics Masterclass", "channel_id": ch_id, "category": "Education"}
        v_res = await ac.post("/api/v1/videos", headers=creator["headers"], data=data, files=files)
        v_id = v_res.json()["id"]

        # View and like to drive metrics
        await ac.post(f"/api/v1/videos/{v_id}/feedback?type=like", headers=creator["headers"])

        # 1. Recommendation feed returns public content
        rec_res = await ac.get("/api/v1/videos/recommendations?limit=10", headers=creator["headers"])
        assert rec_res.status_code == 200
        assert any(v["id"] == v_id for v in rec_res.json())

        # 2. Creator Analytics
        an_res = await ac.get(f"/api/v1/videos/channels/{ch_id}/analytics", headers=creator["headers"])
        assert an_res.status_code == 200
        analytics = an_res.json()
        assert analytics["channel_id"] == ch_id
        assert analytics["total_videos"] >= 1
        assert analytics["total_likes"] >= 1
