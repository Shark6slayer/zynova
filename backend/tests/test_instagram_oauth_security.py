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
