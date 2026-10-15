import pytest
import io
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database.client import connect_to_database, close_database_connection, get_database
from app.core.rate_limit import (
    auth_rate_limiter,
    video_upload_rate_limiter,
    video_comment_rate_limiter
)

@pytest.fixture(autouse=True)
async def init_video_db():
    await connect_to_database()
    auth_rate_limiter.requests.clear()
    video_upload_rate_limiter.requests.clear()
    video_comment_rate_limiter.requests.clear()
    yield
    db = get_database()
    if db is not None:
        await db.users.delete_many({"username": {"$in": ["vid_creator_1", "vid_viewer_2"]}})
        await db.videos.delete_many({"owner_username": {"$in": ["vid_creator_1", "vid_viewer_2"]}})
        await db.video_comments.delete_many({"author_username": {"$in": ["vid_creator_1", "vid_viewer_2"]}})
        await db.video_views.delete_many({})
    await close_database_connection()

@pytest.mark.asyncio
async def test_complete_video_platform_lifecycle():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        db = get_database()
        if db is not None:
            await db.users.delete_many({"username": {"$in": ["vid_creator_1", "vid_viewer_2"]}})
            await db.videos.delete_many({"owner_username": {"$in": ["vid_creator_1", "vid_viewer_2"]}})

        # 1. Register creator and viewer
        reg1 = await client.post("/api/v1/auth/register", json={
            "email": "creator1@superai.in",
            "username": "vid_creator_1",
            "full_name": "Bharat Tech Studio",
            "password": "Password123!"
        })
        assert reg1.status_code == 201

        login1 = await client.post("/api/v1/auth/login", json={
            "email": "creator1@superai.in",
            "password": "Password123!"
        })
        tok1 = login1.json()["access_token"]
        h1 = {"Authorization": f"Bearer {tok1}"}

        reg2 = await client.post("/api/v1/auth/register", json={
            "email": "viewer2@superai.in",
            "username": "vid_viewer_2",
            "full_name": "Kavitha Raman",
            "password": "Password123!"
        })
        assert reg2.status_code == 201

        login2 = await client.post("/api/v1/auth/login", json={
            "email": "viewer2@superai.in",
            "password": "Password123!"
        })
        tok2 = login2.json()["access_token"]
        h2 = {"Authorization": f"Bearer {tok2}"}

        # 2. Upload Video with valid MP4 header
        # Standard MP4 ftyp box header
        mp4_dummy_data = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isomavc1" + (b"\x00" * 1024)
        files = {
            "file": ("sample_benchmark.mp4", io.BytesIO(mp4_dummy_data), "video/mp4")
        }
        data = {
            "title": "Indic Sovereign AI Architecture Overview",
            "description": "Comprehensive review of 2026 foundation models deployed on localized clusters.",
            "visibility": "public"
        }
        upload_res = await client.post("/api/v1/videos", headers=h1, data=data, files=files)
        assert upload_res.status_code == 201
        vid_data = upload_res.json()
        video_id = vid_data["id"]
        assert vid_data["title"] == "Indic Sovereign AI Architecture Overview"
        assert vid_data["owner_username"] == "vid_creator_1"
        assert vid_data["file_size_bytes"] == len(mp4_dummy_data)

        # 3. Test Invalid Video Upload (Non-video file rejected)
        bad_files = {
            "file": ("malicious.exe", io.BytesIO(b"MZ\x90\x00\x03\x00\x00\x00"), "video/mp4")
        }
        bad_res = await client.post("/api/v1/videos", headers=h1, data={"title": "Fake Video"}, files=bad_files)
        assert bad_res.status_code == 400

        # 4. List Public Videos Feed
        feed_res = await client.get("/api/v1/videos?limit=10")
        assert feed_res.status_code == 200
        feed_list = feed_res.json()
        assert any(v["id"] == video_id for v in feed_list)

        # 5. Get Video Details
        detail_res = await client.get(f"/api/v1/videos/{video_id}")
        assert detail_res.status_code == 200
        assert detail_res.json()["id"] == video_id

        # 6. Stream Video with Range Request
        stream_res = await client.get(f"/api/v1/videos/{video_id}/stream", headers={"Range": "bytes=0-100"})
        assert stream_res.status_code == 206
        assert "Content-Range" in stream_res.headers
        assert len(stream_res.content) == 101

        # 7. Record Video View
        view_res1 = await client.post(f"/api/v1/videos/{video_id}/view", headers=h2)
        assert view_res1.status_code == 200
        assert view_res1.json()["recorded"] is True

        # Duplicate view within cooldown window returns recorded: False
        view_res2 = await client.post(f"/api/v1/videos/{video_id}/view", headers=h2)
        assert view_res2.status_code == 200
        assert view_res2.json()["recorded"] is False

        # 8. Like and Unlike Video
        like_res = await client.post(f"/api/v1/videos/{video_id}/like", headers=h2)
        assert like_res.status_code == 200
        assert like_res.json()["likes_count"] == 1
        assert like_res.json()["is_liked"] is True

        unlike_res = await client.delete(f"/api/v1/videos/{video_id}/like", headers=h2)
        assert unlike_res.status_code == 200
        assert unlike_res.json()["likes_count"] == 0
        assert unlike_res.json()["is_liked"] is False

        # 9. Comment Lifecycle
        com_res = await client.post(
            f"/api/v1/videos/{video_id}/comments",
            headers=h2,
            json={"content": "Excellent breakdown of the distributed inference benchmarks!"}
        )
        assert com_res.status_code == 201
        com_data = com_res.json()
        assert com_data["author_username"] == "vid_viewer_2"

        # List comments
        com_list_res = await client.get(f"/api/v1/videos/{video_id}/comments")
        assert com_list_res.status_code == 200
        assert len(com_list_res.json()) >= 1

        # 10. Edit Video Metadata (Ownership check)
        # Unauthorized edit by viewer
        unauth_edit = await client.patch(
            f"/api/v1/videos/{video_id}",
            headers=h2,
            json={"title": "Hacked Title"}
        )
        assert unauth_edit.status_code == 403

        # Authorized edit by creator
        auth_edit = await client.patch(
            f"/api/v1/videos/{video_id}",
            headers=h1,
            json={"title": "Updated Indic Sovereign Architecture 2026"}
        )
        assert auth_edit.status_code == 200
        assert auth_edit.json()["title"] == "Updated Indic Sovereign Architecture 2026"

        # 11. List User Videos & Related Videos
        creator_id = vid_data["owner_id"]
        user_vids = await client.get(f"/api/v1/videos/users/{creator_id}")
        assert user_vids.status_code == 200
        assert any(v["id"] == video_id for v in user_vids.json())

        # Related videos endpoint
        rel_vids = await client.get(f"/api/v1/videos/{video_id}/related")
        assert rel_vids.status_code == 200

        # 12. Delete Video (Unauthorized check)
        del_unauth = await client.delete(f"/api/v1/videos/{video_id}", headers=h2)
        assert del_unauth.status_code == 403

        # Authorized Delete by Creator
        del_auth = await client.delete(f"/api/v1/videos/{video_id}", headers=h1)
        assert del_auth.status_code == 200
        assert del_auth.json()["status"] == "deleted"

        # Verify deletion from feed
        feed_after = await client.get("/api/v1/videos?limit=10")
        assert not any(v["id"] == video_id for v in feed_after.json())
