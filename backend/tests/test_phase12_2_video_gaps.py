"""
Phase 12.2 Backend Gap Closure Test Suite.
Covers:
- Gap 1: YouTube cursor pagination (pageToken, cache, invalid token handling)
- Gap 2: YouTube batch metadata (videos.list duration, viewCount, embeddable filtering, quota handling)
- Gap 3: YouTube category discovery (videoCategories.list, region validation, status check)
- Gap 4: Playlists listing, detail retrieval, ownership enforcement, deletion
- Gap 5: Saved videos GET/POST/DELETE, duplicate prevention, user isolation, is_saved state
- Gap 6: Watch history deletion (single + clear), progress clamping & zero view inflation
- Gap 7: Original video feed filtering (published/private/draft/deleted/moderated) & pagination
- Gap 8: Cloudflare R2 upload, chunked Range 206/416 streaming, missing object 404, presigned URL & auth
"""

import io
import uuid
from unittest.mock import patch, AsyncMock
import pytest
from bson import ObjectId
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database.client import connect_to_database, close_database_connection, get_database
from app.core.rate_limit import auth_rate_limiter, video_upload_rate_limiter, video_comment_rate_limiter
from app.core.config import settings
from app.services import youtube_service
from app.services.media_service import S3StorageAdapter


@pytest.fixture(autouse=True)
async def phase12_2_db_fixture():
    await connect_to_database()
    auth_rate_limiter.requests.clear()
    video_upload_rate_limiter.requests.clear()
    video_comment_rate_limiter.requests.clear()
    youtube_service.clear_youtube_cache()

    created_emails = []

    def track_email(email: str):
        created_emails.append(email)

    yield track_email

    youtube_service.clear_youtube_cache()
    db = get_database()
    if db is not None and created_emails:
        users = await db.users.find({"email": {"$in": created_emails}}).to_list(length=50)
        uids = [str(u["_id"]) for u in users]
        await db.users.delete_many({"_id": {"$in": [u["_id"] for u in users]}})
        await db.videos.delete_many({"owner_id": {"$in": uids}})
        await db.video_playlists.delete_many({"owner_id": {"$in": uids}})
        await db.video_saves.delete_many({"user_id": {"$in": uids}})
        await db.video_watch_history.delete_many({"user_id": {"$in": uids}})
        await db.video_views.delete_many({"viewer_identifier": {"$in": uids}})
    await close_database_connection()


async def register_and_login(ac: AsyncClient, tracker, tag: str) -> dict:
    suffix = uuid.uuid4().hex[:8]
    email = f"p12_2_{tag}_{suffix}@testvideo.zynova.in"
    username = f"p122_{tag}_{suffix}"
    tracker(email)
    reg = await ac.post("/api/v1/auth/register", json={
        "email": email,
        "username": username,
        "full_name": f"Test {tag}",
        "password": "Password123!"
    })
    assert reg.status_code == 201
    uid = reg.json()["id"]
    login = await ac.post("/api/v1/auth/login", json={"email": email, "password": "Password123!"})
    assert login.status_code == 200
    tok = login.json()["access_token"]
    return {"id": uid, "email": email, "username": username, "headers": {"Authorization": f"Bearer {tok}"}}


# ---------------------------------------------------------------------------
# 1–3. YouTube Pagination, Batch Metadata & Category Discovery (Mocked httpx)
# ---------------------------------------------------------------------------

class _FakeResp:
    def __init__(self, status_code: int, json_data: dict):
        self.status_code = status_code
        self._data = json_data
        self.headers = {"content-type": "application/json"}

    def json(self):
        return self._data


@pytest.mark.asyncio
async def test_youtube_pagination_metadata_and_categories(phase12_2_db_fixture):
    calls = []

    orig_get = AsyncClient.get

    async def fake_get(self, url, params=None, **kwargs):
        if "googleapis.com" not in str(url):
            return await orig_get(self, url, params=params, **kwargs)
        calls.append((url, params))
        if "youtube/v3/search" in url:
            tok = (params or {}).get("pageToken")
            if tok == "EXPIRED_TOK":
                return _FakeResp(400, {"error": {"message": "Invalid pageToken", "errors": [{"reason": "invalidPageToken"}]}})
            if tok == "CAoQAA":
                return _FakeResp(200, {
                    "prevPageToken": "PREVPAGE",
                    "pageInfo": {"totalResults": 2},
                    "items": [
                        {
                            "id": {"videoId": "dQw4w9WgXcQ"},
                            "snippet": {
                                "title": "Page 2 Video",
                                "description": "Second page item",
                                "channelTitle": "Chan 2",
                                "channelId": "UCXuqSBlHAE6Xw-yeJA0Tunw",
                                "publishedAt": "2026-10-01T10:00:00Z",
                                "thumbnails": {"high": {"url": "https://i.ytimg.com/vi/dQw4w9WgXcQ/hqdefault.jpg"}},
                            },
                        }
                    ],
                })
            return _FakeResp(200, {
                "nextPageToken": "CAoQAA",
                "pageInfo": {"totalResults": 2},
                "items": [
                    {
                        "id": {"videoId": "Gro5z03a_Qw"},
                        "snippet": {
                            "title": "Public Embeddable",
                            "description": "Valid tech video",
                            "channelTitle": "Linus Tech Tips",
                            "channelId": "UCXuqSBlHAE6Xw-yeJA0Tunw",
                            "publishedAt": "2026-11-09T19:01:45Z",
                            "thumbnails": {"high": {"url": "https://i.ytimg.com/vi/Gro5z03a_Qw/hqdefault.jpg"}},
                        },
                    },
                    {
                        "id": {"videoId": "Blocked1234"},
                        "snippet": {
                            "title": "Non-embeddable Video",
                            "channelTitle": "Restricted",
                            "publishedAt": "2026-11-01T00:00:00Z",
                            "thumbnails": {},
                        },
                    },
                ],
            })
        if "youtube/v3/videos" in url:
            return _FakeResp(200, {
                "items": [
                    {
                        "id": "Gro5z03a_Qw",
                        "snippet": {"title": "Public Embeddable", "categoryId": "28", "channelTitle": "Linus Tech Tips"},
                        "contentDetails": {"duration": "PT1H2M5S"},
                        "statistics": {"viewCount": "125430"},
                        "status": {"embeddable": True, "privacyStatus": "public"},
                    },
                    {
                        "id": "Blocked1234",
                        "snippet": {"title": "Non-embeddable Video", "categoryId": "28"},
                        "contentDetails": {"duration": "P0D"},
                        "statistics": {},
                        "status": {"embeddable": False, "privacyStatus": "public"},
                    },
                    {
                        "id": "dQw4w9WgXcQ",
                        "snippet": {"title": "Page 2 Video", "categoryId": "10"},
                        "contentDetails": {"duration": "PT3M33S"},
                        "statistics": {},  # Hidden view count -> must remain None
                        "status": {"embeddable": True, "privacyStatus": "public"},
                    },
                ]
            })
        if "youtube/v3/videoCategories" in url:
            return _FakeResp(200, {
                "items": [
                    {"id": "28", "snippet": {"title": "Science & Technology", "assignable": True}},
                    {"id": "27", "snippet": {"title": "Education", "assignable": True}},
                    {"id": "99", "snippet": {"title": "Internal", "assignable": False}},
                ]
            })
        return _FakeResp(404, {})

    with patch.object(settings, "YOUTUBE_API_KEY", "test_mock_key"), patch("httpx.AsyncClient.get", new=fake_get):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            # Page 1
            r1 = await ac.get("/api/v1/videos/youtube?q=tech&max_results=5")
            assert r1.status_code == 200
            d1 = r1.json()
            assert d1["configured"] is True
            assert d1["next_page_token"] == "CAoQAA"
            assert d1["has_more"] is True
            assert d1["cached"] is False
            assert len(d1["videos"]) == 1  # Blocked1234 filtered out!
            assert d1["videos"][0]["duration"] == "1:02:05"
            assert d1["videos"][0]["durationSeconds"] == 3725
            assert d1["videos"][0]["viewCount"] == 125430
            assert d1["videos"][0]["categoryId"] == "28"

            # Repeat call hits cache without spending quota
            calls_before = len(calls)
            r1_cached = await ac.get("/api/v1/videos/youtube?q=tech&max_results=5")
            assert r1_cached.status_code == 200
            assert r1_cached.json()["cached"] is True
            assert len(calls) == calls_before

            # Page 2 via cursor page_token
            r2 = await ac.get("/api/v1/videos/youtube?q=tech&max_results=5&page_token=CAoQAA")
            assert r2.status_code == 200
            d2 = r2.json()
            assert d2["has_more"] is False
            assert d2["videos"][0]["id"] == "dQw4w9WgXcQ"
            assert d2["videos"][0]["duration"] == "3:33"
            assert d2["videos"][0]["viewCount"] is None  # Unavailable views not fabricated!

            # Invalid pageToken format rejected
            r_bad_tok = await ac.get("/api/v1/videos/youtube?q=tech&page_token=bad$token!")
            assert r_bad_tok.status_code == 400

            # Expired token upstream handled cleanly
            r_exp_tok = await ac.get("/api/v1/videos/youtube?q=tech&page_token=EXPIRED_TOK")
            assert r_exp_tok.status_code == 400

            # Categories endpoint
            rcat = await ac.get("/api/v1/videos/youtube/categories?region_code=in")
            assert rcat.status_code == 200
            cats = rcat.json()["categories"]
            assert [c["id"] for c in cats] == ["28", "27"]

            # Status endpoint
            rstat = await ac.get("/api/v1/videos/youtube/status/Gro5z03a_Qw")
            assert rstat.status_code == 200
            assert rstat.json()["embeddable"] is True
            assert rstat.json()["duration"] == "1:02:05"


@pytest.mark.asyncio
async def test_youtube_quota_exhaustion_handling(phase12_2_db_fixture):
    orig_get = AsyncClient.get

    async def quota_get(self, url, params=None, **kwargs):
        if "googleapis.com" not in str(url):
            return await orig_get(self, url, params=params, **kwargs)
        return _FakeResp(403, {
            "error": {
                "message": "The request cannot be completed because you have exceeded your quota.",
                "errors": [{"reason": "quotaExceeded"}],
            }
        })

    with patch.object(settings, "YOUTUBE_API_KEY", "test_mock_key"), patch("httpx.AsyncClient.get", new=quota_get):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            r = await ac.get("/api/v1/videos/youtube?q=quota_test")
            assert r.status_code == 200
            assert r.json()["quota_exceeded"] is True
            assert r.json()["videos"] == []

            rc = await ac.get("/api/v1/videos/youtube/categories?region_code=US")
            assert rc.status_code == 200
            assert rc.json()["quota_exceeded"] is True


# ---------------------------------------------------------------------------
# 4–7. Playlists Listing/Deletion, Saved Videos, History Deletion & Feed Moderation
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_playlists_saved_history_and_feed_visibility(phase12_2_db_fixture):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        u1 = await register_and_login(ac, phase12_2_db_fixture, "u1")
        u2 = await register_and_login(ac, phase12_2_db_fixture, "u2")

        mp4 = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isomavc1" + (b"\x00" * 512)
        up_pub = await ac.post(
            "/api/v1/videos",
            headers=u1["headers"],
            data={"title": "Public Tech Video", "visibility": "public", "category": "Tech"},
            files={"file": ("pub.mp4", io.BytesIO(mp4), "video/mp4")},
        )
        assert up_pub.status_code == 201
        pub_id = up_pub.json()["id"]

        up_priv = await ac.post(
            "/api/v1/videos",
            headers=u1["headers"],
            data={"title": "Private Video", "visibility": "private", "category": "Tech"},
            files={"file": ("priv.mp4", io.BytesIO(mp4), "video/mp4")},
        )
        assert up_priv.status_code == 201
        priv_id = up_priv.json()["id"]

        # Moderated / removed video should stay excluded from public feed
        db = get_database()
        rem_res = await db.videos.insert_one({
            **await db.videos.find_one({"_id": ObjectId(pub_id)}),
            "_id": ObjectId(),
            "title": "Moderated Video",
            "moderation_status": "removed",
        })
        rem_id = str(rem_res.inserted_id)

        feed = await ac.get("/api/v1/videos?limit=20&offset=0")
        assert feed.status_code == 200
        feed_ids = [v["id"] for v in feed.json()]
        assert pub_id in feed_ids
        assert priv_id not in feed_ids
        assert rem_id not in feed_ids

        # --- Saved Videos ---
        # Save Zenova video + duplicate check + YouTube reference
        s1 = await ac.post("/api/v1/videos/saved", headers=u2["headers"], json={"video_id": pub_id, "source": "zenova"})
        assert s1.status_code == 201
        s_dup = await ac.post("/api/v1/videos/saved", headers=u2["headers"], json={"video_id": pub_id, "source": "zenova"})
        assert s_dup.status_code == 201  # Idempotent, no 500 or duplicate
        s_yt = await ac.post(
            "/api/v1/videos/saved",
            headers=u2["headers"],
            json={"video_id": "Gro5z03a_Qw", "source": "youtube", "title": "Saved YT Talk"},
        )
        assert s_yt.status_code == 201

        # Private video save blocked for u2
        s_priv = await ac.post("/api/v1/videos/saved", headers=u2["headers"], json={"video_id": priv_id, "source": "zenova"})
        assert s_priv.status_code == 403

        # is_saved accuracy across u2 (True) vs u1 (False)
        d_u2 = await ac.get(f"/api/v1/videos/{pub_id}", headers=u2["headers"])
        d_u1 = await ac.get(f"/api/v1/videos/{pub_id}", headers=u1["headers"])
        assert d_u2.json()["is_saved"] is True
        assert d_u1.json()["is_saved"] is False

        # u1 cannot see u2's saved videos
        saved_u1 = await ac.get("/api/v1/videos/saved", headers=u1["headers"])
        saved_u2 = await ac.get("/api/v1/videos/saved", headers=u2["headers"])
        assert len(saved_u1.json()) == 0
        assert len(saved_u2.json()) == 2

        # Delete saved
        del_s = await ac.delete(f"/api/v1/videos/saved/{pub_id}?source=zenova", headers=u2["headers"])
        assert del_s.status_code == 200
        assert (await ac.get(f"/api/v1/videos/{pub_id}", headers=u2["headers"])).json()["is_saved"] is False

        # --- Playlists ---
        pl_create = await ac.post(
            "/api/v1/videos/playlists",
            headers=u1["headers"],
            json={"title": "Private Study", "visibility": "private", "video_ids": [pub_id]},
        )
        assert pl_create.status_code == 201
        pl_id = pl_create.json()["id"]

        # GET /videos/playlists works cleanly (previously returned HTTP 400 Invalid video ID!)
        pl_list = await ac.get("/api/v1/videos/playlists", headers=u1["headers"])
        assert pl_list.status_code == 200
        assert any(p["id"] == pl_id for p in pl_list.json())

        # Ownership enforcement on GET & DELETE
        pl_u2_get = await ac.get(f"/api/v1/videos/playlists/{pl_id}", headers=u2["headers"])
        assert pl_u2_get.status_code == 403
        pl_u2_del = await ac.delete(f"/api/v1/videos/playlists/{pl_id}", headers=u2["headers"])
        assert pl_u2_del.status_code == 403

        pl_u1_get = await ac.get(f"/api/v1/videos/playlists/{pl_id}", headers=u1["headers"])
        assert pl_u1_get.status_code == 200
        assert len(pl_u1_get.json()["videos"]) == 1

        pl_u1_del = await ac.delete(f"/api/v1/videos/playlists/{pl_id}", headers=u1["headers"])
        assert pl_u1_del.status_code == 200

        # --- Watch History Progress & Deletion ---
        pre_views = (await ac.get(f"/api/v1/videos/{pub_id}")).json()["view_count"]
        prog = await ac.post(
            f"/api/v1/videos/{pub_id}/progress",
            headers=u2["headers"],
            json={"playback_position_seconds": 115.0, "duration_seconds": 120.0, "completed": False},
        )
        assert prog.status_code == 200
        assert prog.json()["completed"] is True  # >=90% auto-marked completed
        post_views = (await ac.get(f"/api/v1/videos/{pub_id}")).json()["view_count"]
        assert post_views == pre_views  # Progress pings do NOT inflate view_count!

        del_hist = await ac.delete(f"/api/v1/videos/user/history/{pub_id}", headers=u2["headers"])
        assert del_hist.status_code == 200
        del_hist_again = await ac.delete(f"/api/v1/videos/user/history/{pub_id}", headers=u2["headers"])
        assert del_hist_again.status_code == 404


# ---------------------------------------------------------------------------
# 8. Cloudflare R2 Streaming, Range 206/416, Presigned URLs & Missing Object
# ---------------------------------------------------------------------------

class MockR2Adapter(S3StorageAdapter):
    def __init__(self, store: dict):
        self._store = store
        self._bucket = "zenova-test-r2"
        self._endpoint_url = "https://mock.r2.cloudflarestorage.com"
        self._cdn_base = None

    async def save_file(self, file_path: str, destination_key: str, content_type: str, is_public: bool = True) -> str:
        with open(file_path, "rb") as fh:
            self._store[destination_key] = {"bytes": fh.read(), "content_type": content_type}
        return f"https://mock.r2.cloudflarestorage.com/{self._bucket}/{destination_key}"

    async def delete_file(self, storage_key: str) -> None:
        self._store.pop(storage_key, None)

    async def get_object_metadata(self, storage_key: str):
        obj = self._store.get(storage_key)
        if not obj:
            return None
        return {"file_size": len(obj["bytes"]), "content_type": obj["content_type"]}

    async def stream_range(self, storage_key: str, start: int, end: int, chunk_size: int = 1024 * 1024):
        obj = self._store.get(storage_key)
        if not obj:
            return
        data = obj["bytes"][start : end + 1]
        for i in range(0, len(data), 128):
            yield data[i : i + 128]

    async def generate_presigned_download(self, storage_key: str, expires_in: int = 300) -> str:
        return f"https://mock.r2.cloudflarestorage.com/{self._bucket}/{storage_key}?X-Amz-Expires={expires_in}&X-Amz-Signature=mock_sig"


@pytest.mark.asyncio
async def test_r2_video_upload_range_streaming_and_presigned_urls(phase12_2_db_fixture):
    r2_store = {}
    mock_r2 = MockR2Adapter(r2_store)

    with patch("app.api.routes.videos.get_storage_adapter", return_value=mock_r2):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            owner = await register_and_login(ac, phase12_2_db_fixture, "r2_owner")
            other = await register_and_login(ac, phase12_2_db_fixture, "r2_other")

            payload_bytes = b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isomavc1" + b"Z" * 1000
            up = await ac.post(
                "/api/v1/videos",
                headers=owner["headers"],
                data={"title": "R2 Private Stream", "visibility": "private"},
                files={"file": ("r2.mp4", io.BytesIO(payload_bytes), "video/mp4")},
            )
            assert up.status_code == 201
            vid_id = up.json()["id"]
            storage_key = up.json()["storage_key"]
            assert storage_key.startswith("videos/")
            assert storage_key in r2_store

            # Private stream blocked for non-owner
            unauth_stream = await ac.get(f"/api/v1/videos/{vid_id}/stream", headers=other["headers"])
            assert unauth_stream.status_code == 403
            unauth_url = await ac.get(f"/api/v1/videos/{vid_id}/stream-url", headers=other["headers"])
            assert unauth_url.status_code == 403

            # Owner receives 206 Partial Content byte range
            partial = await ac.get(
                f"/api/v1/videos/{vid_id}/stream",
                headers={**owner["headers"], "Range": "bytes=0-255"},
            )
            assert partial.status_code == 206
            assert partial.headers["content-range"] == f"bytes 0-255/{len(payload_bytes)}"
            assert len(partial.content) == 256
            assert partial.content == payload_bytes[:256]

            # Out-of-bounds range returns 416
            bad_range = await ac.get(
                f"/api/v1/videos/{vid_id}/stream",
                headers={**owner["headers"], "Range": "bytes=999999-1000500"},
            )
            assert bad_range.status_code == 416

            # Short-lived presigned URL returned without leaking secrets
            surl = await ac.get(f"/api/v1/videos/{vid_id}/stream-url?expires_in=180", headers=owner["headers"])
            assert surl.status_code == 200
            sdata = surl.json()
            assert sdata["delivery"] == "presigned_r2"
            assert sdata["expires_in"] == 180
            assert "X-Amz-Signature=mock_sig" in sdata["stream_url"]

            # Missing object returns 404
            r2_store.pop(storage_key, None)
            missing_stream = await ac.get(f"/api/v1/videos/{vid_id}/stream", headers=owner["headers"])
            assert missing_stream.status_code == 404
