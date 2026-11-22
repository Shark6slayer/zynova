import pytest
import asyncio
from unittest.mock import patch, MagicMock
from app.services.email_service import (
    EmailService,
    EmailAuthException,
    EmailDeliveryException,
    render_verification_email_html,
    render_verification_email_text
)
from app.core.config import settings

def test_email_template_rendering():
    code = "729415"
    html = render_verification_email_html(code, expiration_minutes=5)
    text = render_verification_email_text(code, expiration_minutes=5)

    assert code in html
    assert "ZENOVA" in html
    assert "5 minutes" in html
    assert "Security Notice" in html

    assert code in text
    assert "ZENOVA" in text
    assert "5 minutes" in text

def test_email_service_is_configured():
    # If settings has host, username and password
    with patch.object(settings, "SMTP_PASSWORD", "mock_pass"), \
         patch.object(settings, "SMTP_USERNAME", "no-reply@intellidev.in"), \
         patch.object(settings, "SMTP_HOST", "smtpout.secureserver.net"):
        assert EmailService.is_configured() is True

    with patch.object(settings, "SMTP_PASSWORD", None):
        assert EmailService.is_configured() is False

@pytest.mark.asyncio
async def test_smtp_mocked_success():
    with patch("smtplib.SMTP_SSL") as mock_smtp:
        mock_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_instance

        with patch.object(settings, "SMTP_PASSWORD", "mock_secret"):
            ok, msg = await EmailService.test_connection()
            assert ok is True
            assert "successful" in msg
            mock_instance.login.assert_called_once_with(settings.SMTP_USERNAME, "mock_secret")

@pytest.mark.asyncio
async def test_smtp_mocked_auth_failure():
    import smtplib
    with patch("smtplib.SMTP_SSL") as mock_smtp:
        mock_instance = MagicMock()
        mock_instance.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Authentication credentials invalid")
        mock_smtp.return_value.__enter__.return_value = mock_instance

        with patch.object(settings, "SMTP_PASSWORD", "wrong_secret"):
            ok, msg = await EmailService.test_connection()
            assert ok is False
            assert "535" in msg

@pytest.mark.asyncio
async def test_send_email_mocked_delivery():
    with patch("smtplib.SMTP_SSL") as mock_smtp:
        mock_instance = MagicMock()
        mock_smtp.return_value.__enter__.return_value = mock_instance

        with patch.object(settings, "SMTP_PASSWORD", "valid_secret"):
            result = await EmailService.send_verification_otp(
                to_email="testuser@example.com",
                otp_code="123456"
            )
            assert result is True
            mock_instance.send_message.assert_called_once()
