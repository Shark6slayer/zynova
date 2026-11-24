import pytest
import time
from unittest.mock import patch, MagicMock, AsyncMock
import httpx

from app.core.config import settings
from app.services.catalyst_mail_service import (
    CatalystMailService,
    CatalystOAuthException,
    CatalystDeliveryException
)
from app.services.email_service import (
    EmailService,
    EmailAuthException,
    EmailDeliveryException
)

@pytest.fixture(autouse=True)
def reset_catalyst():
    CatalystMailService.clear_token_cache()
    yield
    CatalystMailService.clear_token_cache()

def test_catalyst_is_configured():
    with patch.object(settings, "CATALYST_PROJECT_ID", "83999000000013024"), \
         patch.object(settings, "CATALYST_CLIENT_ID", "mock_client_id"), \
         patch.object(settings, "CATALYST_CLIENT_SECRET", "mock_client_secret"), \
         patch.object(settings, "CATALYST_REFRESH_TOKEN", "mock_refresh_token"):
        assert CatalystMailService.is_configured() is True

    with patch.object(settings, "CATALYST_CLIENT_ID", None):
        assert CatalystMailService.is_configured() is False

@pytest.mark.asyncio
async def test_oauth_token_refresh_and_caching():
    with patch.object(settings, "CATALYST_CLIENT_ID", "test_id"), \
         patch.object(settings, "CATALYST_CLIENT_SECRET", "test_sec"), \
         patch.object(settings, "CATALYST_REFRESH_TOKEN", "test_rt"), \
         patch.object(settings, "CATALYST_ACCOUNTS_URL", "https://accounts.zoho.in"):

        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "access_token": "zoho_access_token_12345",
            "expires_in": 3600
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

            # 1. First fetch -> calls OAuth endpoint
            t1 = await CatalystMailService.get_access_token()
            assert t1 == "zoho_access_token_12345"
            assert mock_post.call_count == 1

            # 2. Second fetch immediately -> returns cached token without calling endpoint
            t2 = await CatalystMailService.get_access_token()
            assert t2 == "zoho_access_token_12345"
            assert mock_post.call_count == 1

@pytest.mark.asyncio
async def test_oauth_token_renewal_upon_expiry():
    with patch.object(settings, "CATALYST_CLIENT_ID", "test_id"), \
         patch.object(settings, "CATALYST_CLIENT_SECRET", "test_sec"), \
         patch.object(settings, "CATALYST_REFRESH_TOKEN", "test_rt"):

        mock_resp1 = MagicMock()
        mock_resp1.status_code = 200
        mock_resp1.json.return_value = {
            "access_token": "token_first",
            "expires_in": 10  # expires soon
        }

        mock_resp2 = MagicMock()
        mock_resp2.status_code = 200
        mock_resp2.json.return_value = {
            "access_token": "token_renewed",
            "expires_in": 3600
        }

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = [mock_resp1, mock_resp2]

            token1 = await CatalystMailService.get_access_token()
            assert token1 == "token_first"

            # Simulate passage of time past token buffer
            CatalystMailService._token_expires_at = time.time() - 10

            token2 = await CatalystMailService.get_access_token()
            assert token2 == "token_renewed"
            assert mock_post.call_count == 2

@pytest.mark.asyncio
async def test_catalyst_send_email_success():
    with patch.object(settings, "CATALYST_CLIENT_ID", "test_id"), \
         patch.object(settings, "CATALYST_CLIENT_SECRET", "test_sec"), \
         patch.object(settings, "CATALYST_REFRESH_TOKEN", "test_rt"), \
         patch.object(settings, "CATALYST_PROJECT_ID", "83999000000013024"), \
         patch.object(settings, "CATALYST_ENVIRONMENT", "Development"), \
         patch.object(settings, "CATALYST_API_DOMAIN", "https://api.catalyst.zoho.in"), \
         patch.object(CatalystMailService, "get_access_token", return_value="valid_mock_token"):

        mock_send_resp = MagicMock()
        mock_send_resp.status_code = 200
        mock_send_resp.json.return_value = {"status": "success", "message": "Email sent"}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_send_resp

            res = await CatalystMailService.send_email(
                to_email="recipient@example.com",
                subject="Your ZENOVA Verification Code",
                html_content="<p>Code: 123456</p>",
                text_content="Code: 123456"
            )

            assert res["status"] == "success"
            assert mock_post.call_count == 1

            # Verify call arguments: URL, headers, and exact JSON payload keys and types
            call_kwargs = mock_post.call_args.kwargs
            endpoint = mock_post.call_args.args[0]
            assert "83999000000013024" in endpoint
            assert "api.catalyst.zoho.in" in endpoint
            assert endpoint.endswith("/baas/v1/project/83999000000013024/email/send")
            
            # Headers verification
            headers = call_kwargs["headers"]
            assert headers["Authorization"] == "Zoho-oauthtoken valid_mock_token"
            assert headers["Environment"] == "Development"
            assert headers["Content-Type"] == "application/json"

            # Payload keys and exact types verification
            payload = call_kwargs["json"]
            assert set(payload.keys()) == {"from_email", "to_email", "subject", "content", "html_mode"}
            assert isinstance(payload["from_email"], str)
            assert isinstance(payload["to_email"], list)
            assert all(isinstance(x, str) for x in payload["to_email"])
            assert payload["to_email"] == ["recipient@example.com"]
            assert isinstance(payload["subject"], str)
            assert isinstance(payload["content"], str)
            assert isinstance(payload["html_mode"], bool)
            assert payload["html_mode"] is True
            # Assert unsupported fields are NOT in payload
            assert "display_name" not in payload
            assert "text_content" not in payload

@pytest.mark.asyncio
async def test_oauth_failure_handling():
    with patch.object(settings, "CATALYST_CLIENT_ID", "test_id"), \
         patch.object(settings, "CATALYST_CLIENT_SECRET", "test_sec"), \
         patch.object(settings, "CATALYST_REFRESH_TOKEN", "bad_rt"):

        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_resp.json.return_value = {"error": "invalid_client"}

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.return_value = mock_resp

            with pytest.raises(CatalystOAuthException):
                await CatalystMailService.get_access_token()

@pytest.mark.asyncio
async def test_catalyst_api_timeout():
    with patch.object(settings, "CATALYST_CLIENT_ID", "test_id"), \
         patch.object(settings, "CATALYST_CLIENT_SECRET", "test_sec"), \
         patch.object(settings, "CATALYST_REFRESH_TOKEN", "test_rt"), \
         patch.object(CatalystMailService, "get_access_token", return_value="valid_mock_token"):

        with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.TimeoutException("Connection timed out")

            with pytest.raises(CatalystDeliveryException) as excinfo:
                await CatalystMailService.send_email(
                    to_email="test@example.com",
                    subject="Test",
                    html_content="<p>Test</p>"
                )
            assert "timeout" in str(excinfo.value).lower()

@pytest.mark.asyncio
async def test_production_refusal_of_unconfigured_catalyst():
    # If production environment has catalyst configured as provider but credentials missing
    with patch.object(settings, "ENVIRONMENT", "production"), \
         patch.object(settings, "EMAIL_PROVIDER", "catalyst"), \
         patch.object(CatalystMailService, "is_configured", return_value=False):

        with pytest.raises(EmailAuthException):
            await EmailService.send_email(
                to_email="test@example.com",
                subject="Test",
                html_content="<p>Test</p>"
            )

@pytest.mark.asyncio
async def test_production_refusal_of_silent_smtp_failover():
    # If in production and Catalyst sending raises an exception, it must NOT fall back to SMTP
    with patch.object(settings, "ENVIRONMENT", "production"), \
         patch.object(settings, "EMAIL_PROVIDER", "catalyst"), \
         patch.object(CatalystMailService, "is_configured", return_value=True), \
         patch.object(CatalystMailService, "send_email", side_effect=CatalystDeliveryException("Catalyst Gateway Error")):

        with pytest.raises(EmailDeliveryException):
            await EmailService.send_email(
                to_email="test@example.com",
                subject="Test",
                html_content="<p>Test</p>"
            )

def test_environment_variable_alias_precedence():
    # When CATALYST_* is None, effective properties must fall back to ZOHO_* aliases
    with patch.object(settings, "CATALYST_CLIENT_ID", None), \
         patch.object(settings, "ZOHO_CLIENT_ID", "legacy_zoho_id"), \
         patch.object(settings, "CATALYST_CLIENT_SECRET", None), \
         patch.object(settings, "ZOHO_CLIENT_SECRET", "legacy_zoho_sec"), \
         patch.object(settings, "CATALYST_REFRESH_TOKEN", None), \
         patch.object(settings, "ZOHO_REFRESH_TOKEN", "legacy_zoho_rt"), \
         patch.object(settings, "CATALYST_API_BASE_URL", "https://custom.catalyst.api"), \
         patch.object(settings, "CATALYST_DISPLAY_NAME", "Zenova Security"):

        assert settings.effective_catalyst_client_id == "legacy_zoho_id"
        assert settings.effective_catalyst_client_secret == "legacy_zoho_sec"
        assert settings.effective_catalyst_refresh_token == "legacy_zoho_rt"
        assert settings.effective_catalyst_api_domain == "https://custom.catalyst.api"
        assert settings.effective_catalyst_display_name == "Zenova Security"
        assert CatalystMailService.is_configured() is True

def test_catalyst_environment_normalization():
    assert settings.validate_catalyst_environment("development") == "Development"
    assert settings.validate_catalyst_environment("PRODUCTION") == "Production"
    assert settings.validate_catalyst_environment("  Production  ") == "Production"
    assert settings.validate_catalyst_environment("invalid_env") == "Development"

@pytest.mark.asyncio
async def test_catalyst_401_clears_token_cache():
    CatalystMailService._access_token = "stale_token"
    CatalystMailService._token_expires_at = time.time() + 3600

    mock_resp = MagicMock()
    mock_resp.status_code = 401

    with patch.object(settings, "CATALYST_CLIENT_ID", "test_id"), \
         patch.object(settings, "CATALYST_CLIENT_SECRET", "test_sec"), \
         patch.object(settings, "CATALYST_REFRESH_TOKEN", "test_rt"), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        with pytest.raises(CatalystOAuthException) as exc:
            await CatalystMailService.send_email(
                to_email="test@example.com",
                subject="Test",
                html_content="<p>Test</p>"
            )
        assert "HTTP 401" in str(exc.value)
        # Token cache must be wiped
        assert CatalystMailService._access_token is None
        assert CatalystMailService._token_expires_at == 0.0

@pytest.mark.asyncio
async def test_catalyst_500_server_error():
    mock_resp = MagicMock()
    mock_resp.status_code = 500

    with patch.object(settings, "CATALYST_CLIENT_ID", "test_id"), \
         patch.object(settings, "CATALYST_CLIENT_SECRET", "test_sec"), \
         patch.object(settings, "CATALYST_REFRESH_TOKEN", "test_rt"), \
         patch.object(CatalystMailService, "get_access_token", return_value="valid_mock_token"), \
         patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        with pytest.raises(CatalystDeliveryException) as exc:
            await CatalystMailService.send_email(
                to_email="test@example.com",
                subject="Test",
                html_content="<p>Test</p>"
            )
        assert "HTTP 500" in str(exc.value)
