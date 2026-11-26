"""
Test Suite for YouTube Shorts Discovery Engine (Phase 13 / Production Implementation).
Verifies:
1. Endpoint `GET /api/v1/videos/youtube/shorts` exists and returns `YouTubeShortsResponse`.
2. Candidate classification and duration filtering (<= 90 seconds allowed, > 90 seconds excluded).
3. Non-embeddable and private video filtering.
4. Regional and language personalization (Tamil, Hindi, Malayalam, etc.).
5. Quota error resilience (returns quota_exceeded: True without crashing).
6. Invalid pageToken rejection (HTTP 400).
7. Cache hit behavior (cached: True on repeat call).
"""

from unittest.mock import patch
import pytest
import httpx
from httpx import AsyncClient, ASGITransport

from app.main import app
from app.database.client import connect_to_database, close_database_connection
from app.core.config import settings
from app.services import youtube_service

_orig_get = httpx.AsyncClient.get


class MockResponse:
    def __init__(self, status_code: int, json_data: dict):
        self.status_code = status_code
        self._json = json_data
        self.headers = {"content-type": "application/json"}

    def json(self):
        return self._json


@pytest.fixture(autouse=True)
async def shorts_test_fixture():
    await connect_to_database()
    youtube_service.clear_youtube_cache()
    yield
    youtube_service.clear_youtube_cache()
    await close_database_connection()


@pytest.mark.asyncio
async def test_youtube_shorts_unconfigured_api_key():
    """When YOUTUBE_API_KEY is unset, returns configured: False."""
    with patch.object(settings, "YOUTUBE_API_KEY", ""):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.get("/api/v1/videos/youtube/shorts")
            assert res.status_code == 200
            data = res.json()
            assert data["configured"] is False
            assert data["videos"] == []


@pytest.mark.asyncio
async def test_youtube_shorts_candidate_filtering_and_duration():
    """
    Simulates YouTube search.list returning candidate videos, followed by videos.list batch metadata.
    Tests that:
    - Video A (45s, embeddable, public) -> KEPT
    - Video B (180s, embeddable, public) -> FILTERED OUT (exceeds 90s)
    - Video C (30s, non-embeddable) -> FILTERED OUT
    - Video D (60s, embeddable, public) -> KEPT
    """
    mock_search_data = {
        "items": [
            {"id": {"videoId": "shrt_vid_A1"}, "snippet": {"title": "Cool Dance #shorts", "description": "Dancing short", "thumbnails": {"high": {"url": "https://img/a.jpg"}}}},
            {"id": {"videoId": "long_vid_B2"}, "snippet": {"title": "Long Tutorial", "description": "Full tutorial", "thumbnails": {"high": {"url": "https://img/b.jpg"}}}},
            {"id": {"videoId": "no_embed_C3"}, "snippet": {"title": "Restricted #shorts", "description": "No embed", "thumbnails": {"high": {"url": "https://img/c.jpg"}}}},
            {"id": {"videoId": "shrt_vid_D4"}, "snippet": {"title": "Comedy Reel", "description": "Funny clip #shorts", "thumbnails": {"high": {"url": "https://img/d.jpg"}}}},
        ],
        "nextPageToken": "NEXT_PAGE_123",
        "pageInfo": {"totalResults": 4},
    }

    mock_videos_data = {
        "items": [
            {
                "id": "shrt_vid_A1",
                "snippet": {"title": "Cool Dance #shorts", "channelTitle": "Dancer Pro", "categoryId": "10"},
                "contentDetails": {"duration": "PT45S"},
                "statistics": {"viewCount": "150000"},
                "status": {"embeddable": True, "privacyStatus": "public"},
            },
            {
                "id": "long_vid_B2",
                "snippet": {"title": "Long Tutorial", "channelTitle": "Tech Guru", "categoryId": "28"},
                "contentDetails": {"duration": "PT3M"},  # 180s -> should be excluded
                "statistics": {"viewCount": "500000"},
                "status": {"embeddable": True, "privacyStatus": "public"},
            },
            {
                "id": "no_embed_C3",
                "snippet": {"title": "Restricted #shorts", "channelTitle": "Private Creator", "categoryId": "24"},
                "contentDetails": {"duration": "PT30S"},
                "statistics": {"viewCount": "1000"},
                "status": {"embeddable": False, "privacyStatus": "public"},  # Not embeddable
            },
            {
                "id": "shrt_vid_D4",
                "snippet": {"title": "Comedy Reel", "channelTitle": "Comedy Star", "categoryId": "23"},
                "contentDetails": {"duration": "PT1M"},  # 60s -> should be kept
                "statistics": {"viewCount": "89000"},
                "status": {"embeddable": True, "privacyStatus": "public"},
            },
        ]
    }

    async def fake_get(self, url, *args, **kwargs):
        str_url = str(url)
        if "googleapis.com/youtube/v3/search" in str_url:
            return MockResponse(200, mock_search_data)
        elif "googleapis.com/youtube/v3/videos" in str_url:
            return MockResponse(200, mock_videos_data)
        return await _orig_get(self, url, *args, **kwargs)

    with patch.object(settings, "YOUTUBE_API_KEY", "MOCK_VALID_API_KEY"), patch("httpx.AsyncClient.get", new=fake_get):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.get("/api/v1/videos/youtube/shorts?region_code=IN&language=ta")
            assert res.status_code == 200
            data = res.json()
            assert data["configured"] is True
            assert data["region_code"] == "IN"
            assert data["language"] == "ta"
            assert data["next_page_token"] == "NEXT_PAGE_123"

            videos = data["videos"]
            # Only shrt_vid_A1 and shrt_vid_D4 should survive filtering
            v_ids = [v["id"] for v in videos]
            assert "shrt_vid_A1" in v_ids
            assert "shrt_vid_D4" in v_ids
            assert "long_vid_B2" not in v_ids  # Excluded due to > 90s
            assert "no_embed_C3" not in v_ids  # Excluded due to embeddable=False

            for v in videos:
                assert v["is_short_candidate"] is True
                assert v["aspect_ratio"] == "portrait"
                assert v["durationSeconds"] <= 90


@pytest.mark.asyncio
async def test_youtube_shorts_caching():
    """Verifies that repeat calls return cached: True."""
    mock_search = {
        "items": [
            {"id": {"videoId": "cache_test11"}, "snippet": {"title": "Cache Short #shorts", "description": "", "thumbnails": {}}}
        ],
        "pageInfo": {"totalResults": 1},
    }
    mock_meta = {
        "items": [
            {
                "id": "cache_test11",
                "snippet": {"title": "Cache Short #shorts", "channelTitle": "Tester"},
                "contentDetails": {"duration": "PT25S"},
                "statistics": {"viewCount": "100"},
                "status": {"embeddable": True, "privacyStatus": "public"},
            }
        ]
    }

    async def fake_get(self, url, *args, **kwargs):
        str_url = str(url)
        if "googleapis.com/youtube/v3/search" in str_url:
            return MockResponse(200, mock_search)
        elif "googleapis.com/youtube/v3/videos" in str_url:
            return MockResponse(200, mock_meta)
        return await _orig_get(self, url, *args, **kwargs)

    with patch.object(settings, "YOUTUBE_API_KEY", "MOCK_KEY_CACHE"), patch("httpx.AsyncClient.get", new=fake_get):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res1 = await ac.get("/api/v1/videos/youtube/shorts?q=dance")
            assert res1.status_code == 200
            assert res1.json()["cached"] is False

            res2 = await ac.get("/api/v1/videos/youtube/shorts?q=dance")
            assert res2.status_code == 200
            assert res2.json()["cached"] is True


@pytest.mark.asyncio
async def test_youtube_shorts_quota_exceeded():
    """When YouTube returns 403 quota error, service returns quota_exceeded: True gracefully."""
    async def fake_quota_get(self, url, *args, **kwargs):
        str_url = str(url)
        if "googleapis.com/youtube" in str_url:
            return MockResponse(403, {"error": {"message": "The request cannot be completed because you have exceeded your quota.", "errors": [{"reason": "quotaExceeded"}]}})
        return await _orig_get(self, url, *args, **kwargs)

    with patch.object(settings, "YOUTUBE_API_KEY", "MOCK_KEY_QUOTA"), patch("httpx.AsyncClient.get", new=fake_quota_get):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.get("/api/v1/videos/youtube/shorts?q=test")
            assert res.status_code == 200
            data = res.json()
            assert data["quota_exceeded"] is True
            assert data["videos"] == []


@pytest.mark.asyncio
async def test_youtube_shorts_invalid_page_token():
    """Invalid characters in pageToken should return HTTP 400."""
    with patch.object(settings, "YOUTUBE_API_KEY", "MOCK_KEY"):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            res = await ac.get("/api/v1/videos/youtube/shorts?pageToken=INVALID;INJECTION!")
            assert res.status_code == 400
