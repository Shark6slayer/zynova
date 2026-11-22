"""
ZENOVA — Zoho Catalyst Cloud Scale Mail Integration Service
Handles OAuth 2.0 refresh-token flow, access-token caching & renewal,
multipart/form-data payload creation, and API dispatch to Zoho Catalyst Mail.

Official Endpoint:
POST {CATALYST_API_DOMAIN}/baas/v1/project/{CATALYST_PROJECT_ID}/email/send
OAuth Scope: ZohoCatalyst.email.CREATE
Headers:
  Zoho-oauthtoken {access_token}
  Environment: {Development|Production}
"""

import time
import uuid
import asyncio
import logging
from typing import Optional, Dict, Any, Tuple
import httpx

from app.core.config import settings

logger = logging.getLogger("zenova.catalyst_mail")

class CatalystMailException(Exception):
    """Base exception for Catalyst Mail service errors."""
    pass

class CatalystOAuthException(CatalystMailException):
    """OAuth authentication, refresh, or token exchange failure."""
    pass

class CatalystDeliveryException(CatalystMailException):
    """Email delivery rejection or HTTP error from Catalyst API."""
    pass


class CatalystMailService:
    """
    Production-ready asynchronous client for Zoho Catalyst Cloud Scale Mail.
    Manages in-memory token caching with safety buffer and non-blocking token renewal.
    """
    _access_token: Optional[str] = None
    _token_expires_at: float = 0.0
    _lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    def is_configured(cls) -> bool:
        """Checks if required Zoho Catalyst credentials are present in settings (checking effective aliases)."""
        return bool(
            settings.CATALYST_PROJECT_ID
            and settings.effective_catalyst_client_id
            and settings.effective_catalyst_client_secret
            and settings.effective_catalyst_refresh_token
        )

    @classmethod
    def clear_token_cache(cls) -> None:
        """Clears the cached OAuth access token (useful in testing or upon 401)."""
        cls._access_token = None
        cls._token_expires_at = 0.0

    @classmethod
    async def get_access_token(cls, correlation_id: Optional[str] = None) -> str:
        """
        Retrieves a valid access token using the OAuth refresh token.
        Caches the token in memory until 60 seconds before expiration.
        Thread/coroutine safe via asyncio.Lock.
        """
        cid = correlation_id or uuid.uuid4().hex[:12]
        now = time.time()
        if cls._access_token and now < (cls._token_expires_at - 60):
            return cls._access_token

        async with cls._lock:
            # Double-check inside lock
            now = time.time()
            if cls._access_token and now < (cls._token_expires_at - 60):
                return cls._access_token

            if not cls.is_configured():
                logger.error(f"[CatalystOAuth][{cid}] Credentials missing: check CATALYST_CLIENT_ID, CATALYST_CLIENT_SECRET, CATALYST_REFRESH_TOKEN.")
                raise CatalystOAuthException(
                    "Zoho Catalyst Mail credentials are not configured. Check CATALYST_CLIENT_ID, CATALYST_CLIENT_SECRET, and CATALYST_REFRESH_TOKEN."
                )

            # Accounts URL for India DC: https://accounts.zoho.in/oauth/v2/token
            accounts_url = settings.effective_catalyst_accounts_url.rstrip('/')
            token_url = f"{accounts_url}/oauth/v2/token"
            params = {
                "refresh_token": settings.effective_catalyst_refresh_token,
                "client_id": settings.effective_catalyst_client_id,
                "client_secret": settings.effective_catalyst_client_secret,
                "grant_type": "refresh_token",
            }

            try:
                async with httpx.AsyncClient(timeout=settings.CATALYST_REQUEST_TIMEOUT_SECONDS) as client:
                    resp = await client.post(token_url, params=params)
                    
                    if resp.status_code != 200:
                        try:
                            err_data = resp.json()
                            clean_err = str(err_data.get("error") or err_data.get("message") or "")[:120]
                        except Exception:
                            clean_err = resp.text[:120]
                        logger.error(f"[CatalystOAuth][{cid}] Token refresh HTTP {resp.status_code} - sanitized_error={clean_err}")
                        raise CatalystOAuthException(f"OAuth refresh failed with status code {resp.status_code}")

                    data = resp.json()
                    if "error" in data:
                        err_code = data.get("error")
                        logger.error(f"[CatalystOAuth][{cid}] OAuth returned error: {err_code}")
                        raise CatalystOAuthException(f"Catalyst OAuth rejected refresh token: {err_code}")

                    access_token = data.get("access_token")
                    if not access_token:
                        logger.error(f"[CatalystOAuth][{cid}] Access token missing in OAuth response")
                        raise CatalystOAuthException("Access token missing from Catalyst OAuth response")

                    expires_in = int(data.get("expires_in", 3600))
                    cls._access_token = access_token
                    cls._token_expires_at = now + expires_in
                    logger.info(f"[CatalystOAuth][{cid}] Successfully refreshed OAuth access token (HTTP {resp.status_code}, expires_in={expires_in}s).")
                    return access_token

            except httpx.TimeoutException as e:
                logger.error(f"[CatalystOAuth][{cid}] Timeout during OAuth token refresh")
                raise CatalystOAuthException("Catalyst OAuth request timed out") from e
            except httpx.RequestError as e:
                logger.error(f"[CatalystOAuth][{cid}] Network error during OAuth refresh: {type(e).__name__}")
                raise CatalystOAuthException(f"Network error during Catalyst OAuth refresh: {type(e).__name__}") from e

    @classmethod
    async def send_email(
        cls,
        to_email: str,
        subject: str,
        html_content: str,
        text_content: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Sends an email using Zoho Catalyst Cloud Scale Mail REST API.
        Enforces multipart/form-data payload, authorization header, and Environment header.
        """
        cid = uuid.uuid4().hex[:12]
        recipient_domain = to_email.split('@')[-1] if '@' in to_email else 'invalid'
        logger.info(f"[CatalystMail][{cid}] Initiating email dispatch to domain: @{recipient_domain}")

        access_token = await cls.get_access_token(correlation_id=cid)

        api_domain = settings.effective_catalyst_api_domain.rstrip('/')
        project_id = settings.CATALYST_PROJECT_ID
        endpoint_url = f"{api_domain}/baas/v1/project/{project_id}/email/send"

        headers = {
            "Authorization": f"Zoho-oauthtoken {access_token}",
            "Zoho-oauthtoken": access_token,
            "Environment": settings.CATALYST_ENVIRONMENT,
            "X-Catalyst-Environment": settings.CATALYST_ENVIRONMENT,
            "PROJECT_ID": str(project_id),
            "Content-Type": "application/json",
        }

        # Catalyst Cloud Scale Mail REST API payload:
        # from_email, display_name, to_email (list of strings), subject, html_mode, content
        recipients = [to_email] if isinstance(to_email, str) else list(to_email)
        payload = {
            "from_email": settings.CATALYST_FROM_EMAIL,
            "display_name": settings.effective_catalyst_display_name,
            "to_email": recipients,
            "subject": subject,
            "html_mode": "true",
            "content": html_content,
        }
        if text_content:
            payload["text_content"] = text_content

        try:
            async with httpx.AsyncClient(timeout=settings.CATALYST_REQUEST_TIMEOUT_SECONDS) as client:
                resp = await client.post(endpoint_url, headers=headers, json=payload)

                if resp.status_code in (401, 403):
                    # Invalidate token cache in case token was invalidated on server
                    cls.clear_token_cache()
                    logger.warning(f"[CatalystMail][{cid}] Catalyst Mail API returned HTTP {resp.status_code}; invalidated cached token.")
                    raise CatalystOAuthException(f"Catalyst Mail authentication rejected: HTTP {resp.status_code}")

                if resp.status_code not in (200, 201, 202):
                    try:
                        err_data = resp.json()
                        clean_err = str(err_data.get("message") or err_data.get("error") or err_data.get("data") or err_data)[:200]
                    except Exception:
                        clean_err = resp.text[:200]
                    logger.error(f"[CatalystMail][{cid}] Catalyst Mail API HTTP {resp.status_code} - sanitized_msg={clean_err}")
                    raise CatalystDeliveryException(f"Catalyst Mail API error: HTTP {resp.status_code}")

                resp_json = resp.json()
                logger.info(f"[CatalystMail][{cid}] Catalyst Mail dispatch accepted: HTTP {resp.status_code} for @{recipient_domain}")
                return resp_json

        except httpx.TimeoutException as e:
            logger.error(f"[CatalystMail][{cid}] Timeout during Catalyst email dispatch")
            raise CatalystDeliveryException("Timeout while communicating with Zoho Catalyst Mail API") from e
        except httpx.RequestError as e:
            logger.error(f"[CatalystMail][{cid}] Network error during Catalyst email dispatch: {type(e).__name__}")
            raise CatalystDeliveryException(f"Network error during Catalyst email dispatch: {type(e).__name__}") from e
