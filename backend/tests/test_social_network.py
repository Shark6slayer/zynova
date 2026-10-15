import pytest
import io
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.database.client import connect_to_database, close_database_connection, get_database
from app.core.rate_limit import (
    auth_rate_limiter,
    social_post_rate_limiter,
    comment_rate_limiter,
    report_rate_limiter
)

@pytest.fixture(autouse=True)
async def init_social_db():
    await connect_to_database()
    auth_rate_limiter.requests.clear()
    social_post_rate_limiter.requests.clear()
    comment_rate_limiter.requests.clear()
    report_rate_limiter.requests.clear()
    yield
    db = get_database()
    if db is not None:
        await db.users.delete_many({"email": {"$in": ["social_alice@superai.in", "social_bob@superai.in"]}})
        await db.posts.delete_many({})
        await db.follows.delete_many({})
        await db.post_comments.delete_many({})
        await db.reports.delete_many({})
    await close_database_connection()

@pytest.mark.asyncio
async def test_complete_social_network_lifecycle():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        # 1. Register Alice and Bob
        alice_reg = await ac.post("/api/v1/auth/register", json={
            "email": "social_alice@superai.in",
            "username": "alice_indic",
            "full_name": "Alice Indic",
            "password": "Password123!"
        })
        assert alice_reg.status_code == 201
        alice_id = alice_reg.json()["id"]

        bob_reg = await ac.post("/api/v1/auth/register", json={
            "email": "social_bob@superai.in",
            "username": "bob_indic",
            "full_name": "Bob Indic",
            "password": "Password123!"
        })
        assert bob_reg.status_code == 201
        bob_id = bob_reg.json()["id"]

        # 2. Login Alice and Bob
        l_alice = await ac.post("/api/v1/auth/login", json={"email": "social_alice@superai.in", "password": "Password123!"})
        tok_alice = l_alice.json()["access_token"]
        h_alice = {"Authorization": f"Bearer {tok_alice}"}

        l_bob = await ac.post("/api/v1/auth/login", json={"email": "social_bob@superai.in", "password": "Password123!"})
        tok_bob = l_bob.json()["access_token"]
        h_bob = {"Authorization": f"Bearer {tok_bob}"}

        # 3. Follow & Unfollow Lifecycle
        # Alice views Bob's profile
        bob_prof = await ac.get(f"/api/v1/social/profiles/{bob_id}", headers=h_alice)
        assert bob_prof.status_code == 200
        assert bob_prof.json()["followers_count"] == 0
        assert bob_prof.json()["is_following"] is False

        # Self-follow prevented
        self_follow = await ac.post(f"/api/v1/social/profiles/{alice_id}/follow", headers=h_alice)
        assert self_follow.status_code == 400

        # Alice follows Bob
        follow_res = await ac.post(f"/api/v1/social/profiles/{bob_id}/follow", headers=h_alice)
        assert follow_res.status_code == 200

        # Duplicate follow safely handled (idempotent upsert)
        follow_dup = await ac.post(f"/api/v1/social/profiles/{bob_id}/follow", headers=h_alice)
        assert follow_dup.status_code == 200

        # Verify Bob's followers list and count
        bob_prof_after = await ac.get(f"/api/v1/social/profiles/{bob_id}", headers=h_alice)
        assert bob_prof_after.json()["followers_count"] == 1
        assert bob_prof_after.json()["is_following"] is True

        followers_res = await ac.get(f"/api/v1/social/profiles/{bob_id}/followers", headers=h_alice)
        assert followers_res.status_code == 200
        assert any(f["username"] == "alice_indic" for f in followers_res.json())

        # 4. Post Lifecycle
        # Bob creates a post
        post_create_res = await ac.post("/api/v1/social/posts", json={
            "content": "Sovereign AI research paper published today!"
        }, headers=h_bob)
        assert post_create_res.status_code == 201
        post_data = post_create_res.json()
        post_id = post_data["id"]
        assert post_data["author_id"] == bob_id
        assert post_data["is_owner"] is True

        # Alice edits Bob's post (Forbidden)
        illegal_edit = await ac.patch(f"/api/v1/social/posts/{post_id}", json={
            "content": "Hacked content"
        }, headers=h_alice)
        assert illegal_edit.status_code == 403

        # Bob edits his own post
        edit_res = await ac.patch(f"/api/v1/social/posts/{post_id}", json={
            "content": "Sovereign AI research paper published today! (v2 revision)"
        }, headers=h_bob)
        assert edit_res.status_code == 200
        assert edit_res.json()["is_edited"] is True
        assert edit_res.json()["content"] == "Sovereign AI research paper published today! (v2 revision)"

        # 5. Feed Retrieval
        # Alice fetches Following feed (Bob's post should appear)
        following_feed = await ac.get("/api/v1/social/feed?mode=following", headers=h_alice)
        assert following_feed.status_code == 200
        assert any(p["id"] == post_id for p in following_feed.json())

        # Discovery feed
        discovery_feed = await ac.get("/api/v1/social/feed?mode=discovery", headers=h_alice)
        assert discovery_feed.status_code == 200
        assert any(p["id"] == post_id for p in discovery_feed.json())

        # 6. Like & Unlike Post
        # Alice likes Bob's post
        like_res = await ac.post(f"/api/v1/social/posts/{post_id}/like", headers=h_alice)
        assert like_res.status_code == 200
        assert like_res.json()["likes_count"] == 1

        # Duplicate like prevented
        like_dup = await ac.post(f"/api/v1/social/posts/{post_id}/like", headers=h_alice)
        assert like_dup.json()["likes_count"] == 1

        # Check feed reflects Alice liked the post
        alice_check = await ac.get("/api/v1/social/feed?mode=discovery", headers=h_alice)
        target_p = next(p for p in alice_check.json() if p["id"] == post_id)
        assert target_p["is_liked"] is True
        assert target_p["likes_count"] == 1

        # Alice unlikes post
        unlike_res = await ac.delete(f"/api/v1/social/posts/{post_id}/like", headers=h_alice)
        assert unlike_res.status_code == 200
        assert unlike_res.json()["likes_count"] == 0

        # 7. Comment Lifecycle
        # Alice comments on Bob's post
        comm_res = await ac.post(f"/api/v1/social/posts/{post_id}/comments", json={
            "content": "Outstanding breakthrough, Bob!"
        }, headers=h_alice)
        assert comm_res.status_code == 201
        comm_data = comm_res.json()
        comm_id = comm_data["id"]
        assert comm_data["author_id"] == alice_id

        # List comments
        comments_list = await ac.get(f"/api/v1/social/posts/{post_id}/comments", headers=h_bob)
        assert comments_list.status_code == 200
        assert len(comments_list.json()) == 1

        # Alice deletes her comment
        del_comm = await ac.delete(f"/api/v1/social/comments/{comm_id}", headers=h_alice)
        assert del_comm.status_code == 200

        # 8. Content Reporting
        report_res = await ac.post("/api/v1/social/reports", json={
            "target_type": "post",
            "target_id": post_id,
            "reason": "Harassment or Spam",
            "description": "Suspected spam bot activity"
        }, headers=h_alice)
        assert report_res.status_code == 201
        assert report_res.json()["status"] == "pending"

        # Duplicate report rejected
        dup_report = await ac.post("/api/v1/social/reports", json={
            "target_type": "post",
            "target_id": post_id,
            "reason": "Harassment or Spam"
        }, headers=h_alice)
        assert dup_report.status_code == 400

        # 9. Media Upload & Reel Lifecycle
        # Upload valid image
        png_header = b"\x89PNG\r\n\x1a\n" + (b"\x00" * 256)
        files = {"file": ("banner.png", io.BytesIO(png_header), "image/png")}
        img_upload_res = await ac.post("/api/v1/social/media", headers=h_bob, files=files)
        assert img_upload_res.status_code == 201
        uploaded_media = img_upload_res.json()
        assert uploaded_media["media_type"] == "image"
        media_url = uploaded_media["media_url"]

        # Fetch served media
        media_stream = await ac.get(media_url)
        assert media_stream.status_code == 200
        assert media_stream.headers["Content-Type"] == "image/png"

        # Path traversal prevention
        traversal_res = await ac.get("/api/v1/social/media/../../etc/passwd")
        assert traversal_res.status_code in (400, 404)

        # Upload valid short video reel
        mp4_header = b"\x00\x00\x00\x18ftypmp42" + (b"\x00" * 256)
        reel_files = {"file": ("reel.mp4", io.BytesIO(mp4_header), "video/mp4")}
        reel_upload_res = await ac.post("/api/v1/social/media", headers=h_bob, files=reel_files)
        assert reel_upload_res.status_code == 201
        assert reel_upload_res.json()["media_type"] == "video"
        reel_url = reel_upload_res.json()["media_url"]

        # Create a Reel Post
        reel_post_res = await ac.post("/api/v1/social/posts", json={
            "content": "Check out this vertical reel demonstration!",
            "media_url": reel_url,
            "media_type": "video"
        }, headers=h_bob)
        assert reel_post_res.status_code == 201
        reel_post = reel_post_res.json()
        assert reel_post["media_type"] == "video"
        assert reel_post["media_url"] == reel_url

        # Check reels feed
        reels_feed = await ac.get("/api/v1/social/feed?mode=reels")
        assert reels_feed.status_code == 200
        assert any(p["id"] == reel_post["id"] for p in reels_feed.json())

        # Check user posts with video filter
        user_vids = await ac.get(f"/api/v1/social/users/{bob_id}/posts?media_filter=video")
        assert user_vids.status_code == 200
        assert any(p["id"] == reel_post["id"] for p in user_vids.json())

        # 10. Delete Post Authorization
        # Alice cannot delete Bob's post
        illegal_del = await ac.delete(f"/api/v1/social/posts/{post_id}", headers=h_alice)
        assert illegal_del.status_code == 403

        # Bob deletes his post
        good_del = await ac.delete(f"/api/v1/social/posts/{post_id}", headers=h_bob)
        assert good_del.status_code == 200

        # Verify post is deleted from feed
        feed_after = await ac.get("/api/v1/social/feed?mode=discovery", headers=h_alice)
        assert not any(p["id"] == post_id for p in feed_after.json())
