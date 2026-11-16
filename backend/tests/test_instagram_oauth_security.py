"""Tests for Meta / Instagram OAuth redirect URI validation, dialog URL building, and log redaction."""

import logging
import pytest
from app.core.config import Settings, settings
from app.services.meta_instagram_service import MetaInstagramService
from app.main import SensitiveDataRedactionFilter


def test_redirect_uri_validation():
    # Valid plain callback URL
    s_valid = Settings(
        INSTAGRAM_REDIRECT_URI="https://api.zenova.intellidev.in/api/v1/instagram/callback"
    )
    assert s_valid.INSTAGRAM_REDIRECT_URI == "https://api.zenova.intellidev.in/api/v1/instagram/callback"

    # Valid with trailing slash
    s_valid_slash = Settings(
        INSTAGRAM_REDIRECT_URI="https://api.zenova.intellidev.in/api/v1/instagram/callback/"
    )
    assert s_valid_slash.INSTAGRAM_REDIRECT_URI == "https://api.zenova.intellidev.in/api/v1/instagram/callback/"

    # Invalid: Contains query string (e.g. pasted Meta Login URL with params)
    s_invalid_query = Settings(
        INSTAGRAM_REDIRECT_URI="https://www.facebook.com/dialog/oauth?config_id=123&state=abc"
    )
    assert s_invalid_query.INSTAGRAM_REDIRECT_URI == ""

    # Invalid: Not HTTPS
    s_invalid_http = Settings(
        INSTAGRAM_REDIRECT_URI="http://api.zenova.intellidev.in/api/v1/instagram/callback"
    )
    assert s_invalid_http.INSTAGRAM_REDIRECT_URI == ""

    # Invalid: Fragment
    s_invalid_fragment = Settings(
        INSTAGRAM_REDIRECT_URI="https://api.zenova.intellidev.in/api/v1/instagram/callback#fragment"
    )
    assert s_invalid_fragment.INSTAGRAM_REDIRECT_URI == ""

    # Invalid: Wrong path
    s_invalid_path = Settings(
        INSTAGRAM_REDIRECT_URI="https://api.zenova.intellidev.in/api/v1/other/path"
    )
    assert s_invalid_path.INSTAGRAM_REDIRECT_URI == ""


def test_dialog_url_generation_standard(monkeypatch):
    monkeypatch.setattr(settings, "META_APP_ID", "123456789")
    monkeypatch.setattr(settings, "META_APP_SECRET", "super_secret_test")
    monkeypatch.setattr(settings, "META_LOGIN_CONFIG_ID", None)
    monkeypatch.setattr(settings, "INSTAGRAM_REDIRECT_URI", "https://api.zenova.intellidev.in/api/v1/instagram/callback")
    monkeypatch.setattr(settings, "META_GRAPH_VERSION", "v21.0")

    url = MetaInstagramService.get_oauth_dialog_url("test_state_123")
    assert "https://www.facebook.com/v21.0/dialog/oauth" in url
    assert "client_id=123456789" in url
    assert "redirect_uri=https%3A%2F%2Fapi.zenova.intellidev.in%2Fapi%2Fv1%2Finstagram%2Fcallback" in url
    assert "scope=" in url
    assert "config_id=" not in url


def test_dialog_url_generation_with_config_id(monkeypatch):
    monkeypatch.setattr(settings, "META_APP_ID", "123456789")
    monkeypatch.setattr(settings, "META_APP_SECRET", "super_secret_test")
    monkeypatch.setattr(settings, "META_LOGIN_CONFIG_ID", "cfg_987654321")
    monkeypatch.setattr(settings, "INSTAGRAM_REDIRECT_URI", "https://api.zenova.intellidev.in/api/v1/instagram/callback")
    monkeypatch.setattr(settings, "META_GRAPH_VERSION", "v21.0")

    url = MetaInstagramService.get_oauth_dialog_url("test_state_123")
    assert "https://www.facebook.com/v21.0/dialog/oauth" in url
    assert "config_id=cfg_987654321" in url
    assert "override_default_response_type=true" in url
    # Scopes must be omitted when using Meta config_id
    assert "scope=" not in url


def test_sensitive_log_redaction():
    filt = SensitiveDataRedactionFilter()

    # Message string redaction
    rec = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg="GET https://graph.facebook.com/oauth/access_token?client_id=123&client_secret=secret999&code=AQD123xyz&access_token=EAAB123",
        args=(),
        exc_info=None
    )
    filt.filter(rec)
    assert "secret999" not in rec.msg
    assert "AQD123xyz" not in rec.msg
    assert "EAAB123" not in rec.msg
    assert "client_secret=[REDACTED]" in rec.msg
    assert "code=[REDACTED]" in rec.msg
    assert "access_token=[REDACTED]" in rec.msg


@pytest.mark.asyncio
async def test_resolve_instagram_account_granular_scopes(monkeypatch):
    """Path A: Success via debug_token GET with granular_scopes"""
    monkeypatch.setattr(settings, "META_APP_ID", "123")
    monkeypatch.setattr(settings, "META_APP_SECRET", "sec")

    import httpx

    async def mock_post(self, url, **kwargs):
        return httpx.Response(404)

    async def mock_get(self, url, **kwargs):
        url_str = str(url)
        if "debug_token" in url_str:
            return httpx.Response(200, json={
                "data": {
                    "type": "SYSTEM_USER",
                    "is_valid": True,
                    "granular_scopes": [
                        {"scope": "instagram_basic", "target_ids": ["17841461272962386"]},
                        {"scope": "pages_show_list", "target_ids": ["page_111"]}
                    ]
                }
            })
        if "17841461272962386" in url_str:
            return httpx.Response(200, json={
                "id": "17841461272962386",
                "username": "shark_6slayer",
                "profile_picture_url": "https://example.com/pic.jpg",
                "followers_count": 100,
                "media_count": 10
            })
        return httpx.Response(404)

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res = await MetaInstagramService.resolve_instagram_account("mock_user_token_123")
    assert res["ig_user_id"] == "17841461272962386"
    assert res["ig_username"] == "shark_6slayer"
    assert res["token_type"] == "user"
    assert res["access_token"] == "mock_user_token_123"


@pytest.mark.asyncio
async def test_resolve_debug_token_get_fail_post_success(monkeypatch):
    """Step A: debug_token GET fails (e.g. 400), retry POST succeeds"""
    monkeypatch.setattr(settings, "META_APP_ID", "123")
    monkeypatch.setattr(settings, "META_APP_SECRET", "sec")

    import httpx

    async def mock_post(self, url, **kwargs):
        if "debug_token" in str(url):
            return httpx.Response(200, json={
                "data": {
                    "type": "USER",
                    "is_valid": True,
                    "granular_scopes": [
                        {"scope": "instagram_basic", "target_ids": ["17841461272962386"]}
                    ]
                }
            })
        return httpx.Response(404)

    async def mock_get(self, url, **kwargs):
        url_str = str(url)
        if "debug_token" in url_str:
            return httpx.Response(400, json={"error": {"code": 100, "message": "Method not allowed"}})
        if "17841461272962386" in url_str:
            return httpx.Response(200, json={
                "id": "17841461272962386",
                "username": "shark_6slayer"
            })
        return httpx.Response(404)

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res = await MetaInstagramService.resolve_instagram_account("mock_user_token_123")
    assert res["ig_user_id"] == "17841461272962386"
    assert res["ig_username"] == "shark_6slayer"


@pytest.mark.asyncio
async def test_access_log_filter_redacts_code_and_state():
    """Verify that SensitiveDataRedactionFilter redacts code and state query params in uvicorn log lines"""
    filt = SensitiveDataRedactionFilter()
    rec = logging.LogRecord(
        name="uvicorn.access",
        level=logging.INFO,
        pathname="",
        lineno=0,
        msg='127.0.0.1:51234 - "GET /api/v1/instagram/callback?code=AQB_secret_code_999&state=super_secret_state_888 HTTP/1.1" 302',
        args=(),
        exc_info=None
    )
    filt.filter(rec)
    assert "AQB_secret_code_999" not in rec.msg
    assert "super_secret_state_888" not in rec.msg
    assert "code=[REDACTED]" in rec.msg
    assert "state=[REDACTED]" in rec.msg


@pytest.mark.asyncio
async def test_resolve_instagram_account_me_accounts_fallback(monkeypatch):
    """Path B: Success via /me/accounts fallback (classic page-linked)"""
    monkeypatch.setattr(settings, "META_APP_ID", "123")
    monkeypatch.setattr(settings, "META_APP_SECRET", "sec")

    import httpx

    async def mock_post(self, url, **kwargs):
        # debug_token returns empty granular_scopes
        if "debug_token" in str(url):
            return httpx.Response(200, json={"data": {"granular_scopes": []}})
        return httpx.Response(404)

    async def mock_get(self, url, **kwargs):
        url_str = str(url)
        if "/me/accounts" in url_str:
            return httpx.Response(200, json={
                "data": [{
                    "id": "page_999",
                    "name": "My Page",
                    "access_token": "page_token_abc",
                    "instagram_business_account": {
                        "id": "ig_888",
                        "username": "page_ig_user"
                    }
                }]
            })
        if "ig_888" in url_str:
            params = kwargs.get("params", {})
            # Succeeds for page_token
            if params.get("access_token") == "page_token_abc":
                return httpx.Response(200, json={
                    "id": "ig_888",
                    "username": "page_ig_user",
                    "media_count": 5
                })
        return httpx.Response(400)

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res = await MetaInstagramService.resolve_instagram_account("mock_user_token_123")
    assert res["ig_user_id"] == "ig_888"
    assert res["ig_username"] == "page_ig_user"
    assert res["token_type"] == "page"
    assert res["access_token"] == "page_token_abc"
    assert res["page_id"] == "page_999"


@pytest.mark.asyncio
async def test_resolve_instagram_account_nothing_found(monkeypatch):
    """Path failure: No accounts found across any path raises ValueError('no_instagram')"""
    monkeypatch.setattr(settings, "META_APP_ID", "123")
    monkeypatch.setattr(settings, "META_APP_SECRET", "sec")

    import httpx

    async def mock_post(self, url, **kwargs):
        return httpx.Response(200, json={"data": {"granular_scopes": []}})

    async def mock_get(self, url, **kwargs):
        return httpx.Response(200, json={"data": []})

    monkeypatch.setattr(httpx.AsyncClient, "post", mock_post)
    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    with pytest.raises(ValueError) as exc_info:
        await MetaInstagramService.resolve_instagram_account("mock_user_token_123")
    assert "no_instagram" in str(exc_info.value)


@pytest.mark.asyncio
async def test_fetch_media_uses_stored_token_correctly(monkeypatch):
    """Verifies fetch_instagram_media uses the passed token (user or page) in request headers/params"""
    import httpx

    captured_params = {}

    async def mock_get(self, url, **kwargs):
        nonlocal captured_params
        captured_params = kwargs.get("params", {})
        return httpx.Response(200, json={
            "data": [{"id": "media_test_1", "media_type": "IMAGE", "caption": "Hello world"}],
            "paging": {"cursors": {"after": "next_page"}}
        })

    monkeypatch.setattr(httpx.AsyncClient, "get", mock_get)

    res = await MetaInstagramService.fetch_instagram_media(
        ig_user_id="17841461272962386",
        page_token="stored_user_token_abc"
    )
    assert len(res["data"]) == 1
    assert captured_params.get("access_token") == "stored_user_token_abc"


