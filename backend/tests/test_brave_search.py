import pytest
import httpx
from httpx import AsyncClient, ASGITransport, Response
from unittest.mock import patch
from app.main import app
from app.core.config import settings

@pytest.mark.asyncio
async def test_brave_search_unconfigured():
    orig_key = settings.BRAVE_SEARCH_API_KEY
    settings.BRAVE_SEARCH_API_KEY = None
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            resp = await client.get("/api/v1/search/brave?q=test")
            assert resp.status_code == 200
            data = resp.json()
            assert data["configured"] is False
            assert data["provider"] == "brave"
            assert "Brave Search API credential (BRAVE_SEARCH_API_KEY)" in data["message"]
            assert data["fallback_url"] == "https://search.brave.com/search?q=test"
            assert "google" not in data["message"].lower()

            # Test web alias
            resp_web = await client.get("/api/v1/search/web?q=test")
            assert resp_web.status_code == 200
            assert resp_web.json()["configured"] is False

            # Test google alias (which now routes to brave)
            resp_google = await client.get("/api/v1/search/google?q=test")
            assert resp_google.status_code == 200
            assert resp_google.json()["provider"] == "brave"
    finally:
        settings.BRAVE_SEARCH_API_KEY = orig_key

@pytest.mark.asyncio
async def test_brave_search_success_mock():
    orig_key = settings.BRAVE_SEARCH_API_KEY
    settings.BRAVE_SEARCH_API_KEY = "test_brave_key_mock_12345"

    fake_brave_response = {
        "query": {
            "original": "quantum computing"
        },
        "web": {
            "total": 42000,
            "results": [
                {
                    "title": "Quantum Computing Fundamentals",
                    "url": "https://quantum.example.org/guide",
                    "description": "Comprehensive overview of qubits, superposition, and quantum supremacy.",
                    "profile": {
                        "name": "quantum.example.org",
                        "img": "https://quantum.example.org/favicon.png"
                    },
                    "thumbnail": {
                        "src": "https://quantum.example.org/thumb.jpg"
                    }
                },
                {
                    "title": "Latest Advances in Quantum Processors",
                    "url": "https://tech-news.example.com/quantum-2026",
                    "description": "Researchers reveal 1000-qubit fault-tolerant quantum architecture.",
                    "profile": {
                        "name": "tech-news.example.com"
                    }
                }
            ]
        }
    }

    orig_get = httpx.AsyncClient.get
    async def selective_get(self, url, *args, **kwargs):
        if "api.search.brave.com" in str(url):
            return Response(
                status_code=200,
                json=fake_brave_response,
                headers={"content-type": "application/json"}
            )
        return await orig_get(self, url, *args, **kwargs)

    try:
        with patch.object(httpx.AsyncClient, "get", selective_get):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                resp = await client.get("/api/v1/search/brave?q=quantum%20computing")
                assert resp.status_code == 200
                data = resp.json()
                assert data["configured"] is True
                assert data["provider"] == "brave"
                assert data["query"] == "quantum computing"
                assert data["total_results"] == 42000
                assert len(data["items"]) == 2

                item1 = data["items"][0]
                assert item1["title"] == "Quantum Computing Fundamentals"
                assert item1["link"] == "https://quantum.example.org/guide"
                assert item1["snippet"] == "Comprehensive overview of qubits, superposition, and quantum supremacy."
                assert item1["displayLink"] == "quantum.example.org"
                assert item1["thumbnailUrl"] == "https://quantum.example.org/thumb.jpg"

                item2 = data["items"][1]
                assert item2["title"] == "Latest Advances in Quantum Processors"
                assert item2["link"] == "https://tech-news.example.com/quantum-2026"
                assert item2["snippet"] == "Researchers reveal 1000-qubit fault-tolerant quantum architecture."
                assert item2["displayLink"] == "tech-news.example.com"
                assert item2["thumbnailUrl"] is None
    finally:
        settings.BRAVE_SEARCH_API_KEY = orig_key
