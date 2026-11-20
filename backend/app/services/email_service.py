import asyncio
import smtplib
import ssl
import logging
from email.message import EmailMessage
from email.utils import formataddr
from typing import Optional, Dict, Any, Tuple
from app.core.config import settings

logger = logging.getLogger("super_ai.email_service")

class EmailServiceException(Exception):
    """Base exception for transactional email service errors."""
    pass

class EmailAuthException(EmailServiceException):
    """SMTP authentication failure."""
    pass

class EmailConnectionException(EmailServiceException):
    """SMTP network or SSL connection failure."""
    pass

class EmailDeliveryException(EmailServiceException):
    """SMTP recipient or data delivery failure."""
    pass

def render_verification_email_html(code: str, expiration_minutes: int = 5) -> str:
    """Renders a responsive, modern HTML email template for email verification."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SUPER_AI Verification Code</title>
  <style>
    body {{
      margin: 0;
      padding: 0;
      background-color: #0b0f19;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      color: #f3f4f6;
    }}
    .wrapper {{
      width: 100%;
      background-color: #0b0f19;
      padding: 40px 15px;
      box-sizing: border-box;
    }}
    .container {{
      max-width: 560px;
      margin: 0 auto;
      background: #111827;
      border: 1px solid #1f2937;
      border-radius: 16px;
      padding: 36px 32px;
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.4);
    }}
    .header {{
      text-align: center;
      margin-bottom: 28px;
    }}
    .badge {{
      display: inline-block;
      padding: 6px 14px;
      border-radius: 9999px;
      background: rgba(139, 92, 246, 0.15);
      border: 1px solid rgba(139, 92, 246, 0.4);
      color: #a78bfa;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      margin-bottom: 12px;
    }}
    .title {{
      font-size: 24px;
      font-weight: 700;
      color: #ffffff;
      margin: 0 0 8px 0;
    }}
    .subtitle {{
      font-size: 14px;
      color: #9ca3af;
      margin: 0;
      line-height: 1.5;
    }}
    .otp-box {{
      background: #1f2937;
      border: 1px solid #374151;
      border-radius: 12px;
      padding: 24px;
      text-align: center;
      margin: 28px 0;
    }}
    .otp-label {{
      font-size: 12px;
      font-weight: 500;
      color: #9ca3af;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 8px;
    }}
    .otp-code {{
      font-family: 'Courier New', Courier, monospace;
      font-size: 38px;
      font-weight: 800;
      letter-spacing: 8px;
      color: #8b5cf6;
      margin: 0;
    }}
    .info-list {{
      font-size: 13px;
      color: #9ca3af;
      line-height: 1.6;
      background: rgba(255, 255, 255, 0.02);
      border-radius: 10px;
      padding: 16px 20px;
      margin-bottom: 24px;
    }}
    .info-item {{
      margin-bottom: 6px;
    }}
    .warning {{
      font-size: 12px;
      color: #f87171;
      line-height: 1.5;
      border-left: 3px solid #ef4444;
      padding-left: 12px;
      margin: 20px 0;
    }}
    .footer {{
      border-top: 1px solid #1f2937;
      padding-top: 20px;
      text-align: center;
      font-size: 12px;
      color: #6b7280;
      line-height: 1.5;
    }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="container">
      <div class="header">
        <div class="badge">Sovereign Identity</div>
        <h1 class="title">Verify Your Email Address</h1>
        <p class="subtitle">Use the verification code below to complete your SUPER_AI registration and secure your sovereign account.</p>
      </div>

      <div class="otp-box">
        <div class="otp-label">Verification Code</div>
        <div class="otp-code">{code}</div>
      </div>

      <div class="info-list">
        <div class="info-item">&#9201; <strong>Valid for:</strong> {expiration_minutes} minutes</div>
        <div class="info-item">&#128274; <strong>Security:</strong> Single-use code. Will expire after 5 incorrect attempts.</div>
      </div>

      <div class="warning">
        <strong>Security Notice:</strong> Never share this code with anyone. SUPER_AI representatives will never ask for your verification code or password.
      </div>

      <div class="footer">
        &copy; 2026 SUPER_AI &bull; IntelliDev Technologies<br>
        This is an automated operational security message. Please do not reply directly to this email.
      </div>
    </div>
  </div>
</body>
</html>"""

def render_verification_email_text(code: str, expiration_minutes: int = 5) -> str:
    """Renders plain-text email verification content."""
    return f"""SUPER_AI - Verify Your Email Address

Use the 6-digit verification code below to confirm your email and complete your SUPER_AI registration:

VERIFICATION CODE: {code}

- Valid for: {expiration_minutes} minutes
- Security: Single-use code. Invalidated after 5 failed attempts or upon successful verification.

SECURITY NOTICE:
Never share this code with anyone. SUPER_AI will never contact you asking for your verification code. If you did not request this email, you can safely ignore it.

---
SUPER_AI | IntelliDev Technologies
Automated system notification. Do not reply to this email.
"""

class EmailService:
    """
    Production-ready asynchronous-compatible Email Service.
    Supports GoDaddy Professional Email (Titan) SSL SMTP on port 465.
    Threadpool offloaded to prevent blocking FastAPI's async event loop.
    """

    @classmethod
    def is_configured(cls) -> bool:
        """Checks whether SMTP credentials and host are configured."""
        return bool(settings.SMTP_HOST and settings.SMTP_USERNAME and settings.SMTP_PASSWORD)

    @classmethod
    def _create_ssl_context(cls) -> ssl.SSLContext:
        """Creates a verified default SSL context."""
        context = ssl.create_default_context()
        return context

    @classmethod
    def _test_connection_sync(cls) -> Tuple[bool, str]:
        """
        Synchronous worker for testing SMTP SSL connectivity and authentication.
        Safe: Never logs or returns raw passwords.
        """
        if not cls.is_configured():
            return False, "SMTP is not fully configured (missing SMTP_PASSWORD or host settings in environment)"

        context = cls._create_ssl_context()
        try:
            # GoDaddy Titan uses SMTPS (Implicit SSL) on port 465
            if settings.SMTP_USE_SSL:
                with smtplib.SMTP_SSL(
                    host=settings.SMTP_HOST,
                    port=settings.SMTP_PORT,
                    timeout=settings.SMTP_TIMEOUT_SECONDS,
                    context=context
                ) as server:
                    server.ehlo()
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                    return True, "SMTP connection and authentication successful"
            else:
                with smtplib.SMTP(
                    host=settings.SMTP_HOST,
                    port=settings.SMTP_PORT,
                    timeout=settings.SMTP_TIMEOUT_SECONDS
                ) as server:
                    server.ehlo()
                    server.starttls(context=context)
                    server.ehlo()
                    server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                    return True, "SMTP STARTTLS connection and authentication successful"
        except smtplib.SMTPAuthenticationError as e:
            msg = f"SMTP Authentication failed (code {e.smtp_code})"
            logger.error(msg)
            return False, msg
        except smtplib.SMTPConnectError as e:
            msg = f"SMTP Connection failed: {e}"
            logger.error(msg)
            return False, msg
        except (smtplib.SMTPServerDisconnected, TimeoutError, OSError) as e:
            msg = f"SMTP Network/Timeout error: {type(e).__name__}"
            logger.error(msg)
            return False, msg
        except Exception as e:
            msg = f"Unexpected SMTP error: {type(e).__name__}"
            logger.error(msg)
            return False, msg

    @classmethod
    async def test_connection(cls) -> Tuple[bool, str]:
        """Asynchronously tests SMTP connectivity and credentials without blocking event loop."""
        return await asyncio.to_thread(cls._test_connection_sync)

    @classmethod
    def _send_email_sync(
        cls,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str
    ) -> bool:
        """
        Synchronous SMTP sender with exponential backoff retry.
        Runs inside an asyncio thread pool worker.
        """
        if not cls.is_configured():
            raise EmailAuthException("SMTP_PASSWORD or required configuration is not set in environment.")

        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = formataddr((settings.SMTP_FROM_NAME, settings.SMTP_FROM_EMAIL))
        msg["To"] = to_email
        msg.set_content(text_content)
        msg.add_alternative(html_content, subtype="html")

        context = cls._create_ssl_context()
        retries = settings.SMTP_MAX_RETRIES
        delay = settings.SMTP_RETRY_DELAY_SECONDS

        last_error: Optional[Exception] = None

        for attempt in range(1, retries + 1):
            try:
                if settings.SMTP_USE_SSL:
                    with smtplib.SMTP_SSL(
                        host=settings.SMTP_HOST,
                        port=settings.SMTP_PORT,
                        timeout=settings.SMTP_TIMEOUT_SECONDS,
                        context=context
                    ) as server:
                        server.ehlo()
                        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                        server.send_message(msg)
                else:
                    with smtplib.SMTP(
                        host=settings.SMTP_HOST,
                        port=settings.SMTP_PORT,
                        timeout=settings.SMTP_TIMEOUT_SECONDS
                    ) as server:
                        server.ehlo()
                        server.starttls(context=context)
                        server.ehlo()
                        server.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
                        server.send_message(msg)

                logger.info(f"Transactional email successfully delivered to recipient domain: {to_email.split('@')[-1]}")
                return True

            except smtplib.SMTPAuthenticationError as e:
                logger.error(f"SMTP Auth error on attempt {attempt}: code {e.smtp_code}")
                raise EmailAuthException(f"SMTP authentication rejected (code {e.smtp_code})")
            except (smtplib.SMTPConnectError, smtplib.SMTPServerDisconnected, TimeoutError, OSError) as e:
                last_error = e
                logger.warning(f"SMTP connection issue on attempt {attempt}/{retries}: {type(e).__name__}")
                if attempt < retries:
                    import time
                    time.sleep(delay)
                    delay *= 2
            except smtplib.SMTPException as e:
                last_error = e
                logger.error(f"SMTP delivery error on attempt {attempt}: {type(e).__name__}")
                if attempt < retries:
                    import time
                    time.sleep(delay)
                    delay *= 2

        raise EmailDeliveryException(f"Failed to deliver email after {retries} attempts: {type(last_error).__name__}")

    @classmethod
    async def send_email(
        cls,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: str
    ) -> bool:
        """Asynchronously dispatches an email via threadpool offload."""
        return await asyncio.to_thread(
            cls._send_email_sync,
            to_email,
            subject,
            html_content,
            text_content
        )

    @classmethod
    async def send_verification_otp(cls, to_email: str, otp_code: str, expiration_minutes: int = 5) -> bool:
        """
        Sends the 6-digit verification OTP email to a user.
        Uses the responsive SUPER_AI template.
        """
        subject = "SUPER_AI – Verify Your Email Address"
        html = render_verification_email_html(code=otp_code, expiration_minutes=expiration_minutes)
        text = render_verification_email_text(code=otp_code, expiration_minutes=expiration_minutes)
        return await cls.send_email(to_email=to_email, subject=subject, html_content=html, text_content=text)

    @classmethod
    async def send_password_reset_otp(cls, to_email: str, reset_code: str, expiration_minutes: int = 10) -> bool:
        """
        Sends the 6-digit password reset code email to a user.
        Uses the responsive SUPER_AI template.
        """
        subject = "SUPER_AI – Password Reset Request"
        html = render_password_reset_email_html(code=reset_code, expiration_minutes=expiration_minutes)
        text = render_password_reset_email_text(code=reset_code, expiration_minutes=expiration_minutes)
        return await cls.send_email(to_email=to_email, subject=subject, html_content=html, text_content=text)


def render_password_reset_email_html(code: str, expiration_minutes: int = 10) -> str:
    """Renders a responsive, modern HTML email template for password reset."""
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>SUPER_AI Password Reset</title>
  <style>
    body {{
      margin: 0;
      padding: 0;
      background-color: #0b0f19;
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
      color: #f3f4f6;
    }}
    .wrapper {{
      width: 100%;
      background-color: #0b0f19;
      padding: 40px 15px;
      box-sizing: border-box;
    }}
    .container {{
      max-width: 560px;
      margin: 0 auto;
      background: #111827;
      border: 1px solid #1f2937;
      border-radius: 16px;
      padding: 36px 32px;
      box-shadow: 0 10px 25px rgba(0, 0, 0, 0.4);
    }}
    .header {{
      text-align: center;
      margin-bottom: 28px;
    }}
    .badge {{
      display: inline-block;
      padding: 6px 14px;
      border-radius: 9999px;
      background: rgba(239, 68, 68, 0.15);
      border: 1px solid rgba(239, 68, 68, 0.4);
      color: #f87171;
      font-size: 12px;
      font-weight: 600;
      letter-spacing: 0.05em;
      text-transform: uppercase;
      margin-bottom: 12px;
    }}
    .title {{
      font-size: 24px;
      font-weight: 700;
      color: #ffffff;
      margin: 0 0 8px 0;
    }}
    .subtitle {{
      font-size: 14px;
      color: #9ca3af;
      margin: 0;
      line-height: 1.5;
    }}
    .otp-box {{
      background: #1f2937;
      border: 1px solid #374151;
      border-radius: 12px;
      padding: 24px;
      text-align: center;
      margin: 28px 0;
    }}
    .otp-label {{
      font-size: 12px;
      font-weight: 500;
      color: #9ca3af;
      text-transform: uppercase;
      letter-spacing: 0.05em;
      margin-bottom: 8px;
    }}
    .otp-code {{
      font-family: 'Courier New', Courier, monospace;
      font-size: 38px;
      font-weight: 800;
      letter-spacing: 8px;
      color: #f87171;
      margin: 0;
    }}
    .info-list {{
      font-size: 13px;
      color: #9ca3af;
      line-height: 1.6;
      background: rgba(255, 255, 255, 0.02);
      border-radius: 10px;
      padding: 16px 20px;
      margin-bottom: 24px;
    }}
    .info-item {{
      margin-bottom: 6px;
    }}
    .warning {{
      font-size: 12px;
      color: #fca5a5;
      line-height: 1.5;
      border-left: 3px solid #ef4444;
      padding-left: 12px;
      margin: 20px 0;
    }}
    .footer {{
      border-top: 1px solid #1f2937;
      padding-top: 20px;
      text-align: center;
      font-size: 12px;
      color: #6b7280;
      line-height: 1.5;
    }}
  </style>
</head>
<body>
  <div class="wrapper">
    <div class="container">
      <div class="header">
        <div class="badge">Security Alert</div>
        <h1 class="title">Password Reset Request</h1>
        <p class="subtitle">We received a request to reset your SUPER_AI account password. Use the 6-digit verification code below to proceed.</p>
      </div>

      <div class="otp-box">
        <div class="otp-label">Password Reset Code</div>
        <div class="otp-code">{code}</div>
      </div>

      <div class="info-list">
        <div class="info-item">&#9201; <strong>Valid for:</strong> {expiration_minutes} minutes</div>
        <div class="info-item">&#128274; <strong>Security:</strong> Single-use code. Invalidated after 5 failed attempts or upon successful reset.</div>
      </div>

      <div class="warning">
        <strong>Important:</strong> If you did not request this password reset, please ignore this email. Your password will remain unchanged and your account is secure. Never share this code with anyone.
      </div>

      <div class="footer">
        &copy; 2026 SUPER_AI &bull; IntelliDev Technologies<br>
        This is an automated operational security message. Please do not reply directly to this email.
      </div>
    </div>
  </div>
</body>
</html>"""


def render_password_reset_email_text(code: str, expiration_minutes: int = 10) -> str:
    """Renders plain-text password reset email content."""
    return f"""SUPER_AI – Password Reset Request

We received a request to reset the password for your SUPER_AI account.

RESET CODE: {code}

- Valid for: {expiration_minutes} minutes
- Security: Single-use code. Invalidated after 5 failed attempts or upon successful reset.

SECURITY NOTICE:
If you did not request a password reset, you can safely ignore this email. Your password will remain unchanged. Never share this code with anyone.

---
SUPER_AI | IntelliDev Technologies
Automated system notification. Do not reply to this email.
"""
