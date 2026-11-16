import os
import json
import base64
import hmac
import hashlib
import urllib.parse
import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime, timezone, timedelta
import httpx
from bson import ObjectId

from app.core.config import settings
from app.core.rate_limit import get_redis_client
from app.core.crypto_kms import encrypt_field, decrypt_field
from app.services.media_service import get_storage_adapter, MIME_CONFIG, _validate_magic, QUARANTINE_DIR, _safe_remove

logger = logging.getLogger("zynova.meta_instagram_service")

# Meta Graph API Base URLs
OAUTH_DIALOG_BASE = "https://www.facebook.com"
GRAPH_BASE = "https://graph.facebook.com"

# Requested Scopes per Hard Rules
META_SCOPES = [
    "instagram_basic",
    "instagram_manage_insights",
    "pages_show_list",
    "pages_read_engagement"
]

class MetaInstagramService:
    @staticmethod
    def is_configured() -> bool:
        """Verifies if Meta App ID, Secret, and a valid plain redirect URI are configured."""
        return bool(
            settings.META_APP_ID
            and settings.META_APP_SECRET
            and settings.INSTAGRAM_REDIRECT_URI
        )

    @staticmethod
    def get_version() -> str:
        return settings.META_GRAPH_VERSION or "v21.0"

    @classmethod
    def get_oauth_dialog_url(cls, state: str) -> str:
        """
        Builds Meta OAuth Dialog URL:
        https://www.facebook.com/{META_GRAPH_VERSION}/dialog/oauth

        If META_LOGIN_CONFIG_ID is configured (Facebook Login for Business):
          - Adds config_id={META_LOGIN_CONFIG_ID}
          - Adds override_default_response_type=true
          - Omits scope (managed by Meta configuration)
        Otherwise:
          - Uses standard permissions scope list
        """
        version = cls.get_version()
        client_id = settings.META_APP_ID or ""
        redirect_uri = settings.INSTAGRAM_REDIRECT_URI or ""

        params = [
            ("client_id", client_id),
            ("redirect_uri", redirect_uri),
            ("response_type", "code"),
            ("state", state),
        ]

        if settings.META_LOGIN_CONFIG_ID:
            params.append(("config_id", settings.META_LOGIN_CONFIG_ID))
            params.append(("override_default_response_type", "true"))
        else:
            scopes_str = ",".join(META_SCOPES)
            params.append(("scope", scopes_str))

        query_string = urllib.parse.urlencode(params)
        return f"{OAUTH_DIALOG_BASE}/{version}/dialog/oauth?{query_string}"

    # ---------------------------------------------------------------------------
    # Redis State Management (Atomic Get + Delete, 600s TTL)
    # ---------------------------------------------------------------------------

    # Fallback in-memory state dictionary when Redis is not running in test/dev
    _local_state_store: Dict[str, Tuple[Dict[str, Any], float]] = {}

    @classmethod
    async def store_state(cls, state: str, user_id: str, platform: str) -> None:
        """Stores state with user_id & platform. TTL = 600s."""
        data_json = json.dumps({"user_id": user_id, "platform": platform})
        r_client = await get_redis_client()
        if r_client is not None:
            try:
                await r_client.set(f"ig_state:{state}", data_json, ex=600)
                return
            except Exception as e:
                logger.warning(f"Redis store_state error: {e}. Using local fallback.")
        cls._local_state_store[f"ig_state:{state}"] = ({"user_id": user_id, "platform": platform}, datetime.now(timezone.utc).timestamp() + 600)

    @classmethod
    async def get_and_delete_state(cls, state: str) -> Optional[Dict[str, Any]]:
        """Atomically retrieves and deletes state to prevent replay attacks."""
        key = f"ig_state:{state}"
        r_client = await get_redis_client()
        if r_client is not None:
            try:
                # Redis pipeline for atomic GET + DEL
                pipe = r_client.pipeline()
                pipe.get(key)
                pipe.delete(key)
                results = await pipe.execute()
                val = results[0]
                if val:
                    return json.loads(val)
                return None
            except Exception as e:
                logger.warning(f"Redis get_and_delete_state error: {e}. Checking local fallback.")

        # Local fallback
        record = cls._local_state_store.pop(key, None)
        if record:
            data, exp = record
            if datetime.now(timezone.utc).timestamp() <= exp:
                return data
        return None

    # ---------------------------------------------------------------------------
    # Token Exchange Flow
    # ---------------------------------------------------------------------------

    @staticmethod
    def _log_graph_error(step: str, resp: httpx.Response) -> Dict[str, Any]:
        """
        Extracts and logs Meta Graph API error details safely without logging secrets or URLs.
        Only logs: step, HTTP status, error.code, error.error_subcode, error.type, error.message, fbtrace_id.
        """
        err_details: Dict[str, Any] = {
            "step": step,
            "status_code": resp.status_code,
            "code": None,
            "error_subcode": None,
            "type": None,
            "message": None,
            "fbtrace_id": None,
        }
        try:
            body = resp.json()
            if isinstance(body, dict) and "error" in body:
                e = body["error"]
                if isinstance(e, dict):
                    err_details["code"] = e.get("code")
                    err_details["error_subcode"] = e.get("error_subcode")
                    err_details["type"] = e.get("type")
                    err_details["message"] = e.get("message")
                    err_details["fbtrace_id"] = e.get("fbtrace_id")
        except Exception:
            pass

        logger.error(
            f"Meta Graph API Error during '{step}': status={err_details['status_code']} "
            f"code={err_details['code']} subcode={err_details['error_subcode']} "
            f"type='{err_details['type']}' message='{err_details['message']}' "
            f"fbtrace_id='{err_details['fbtrace_id']}'"
        )
        return err_details

    @classmethod
    async def exchange_code_for_user_token(cls, code: str) -> str:
        """
        Exchanges authorization code for a short-lived user access token.
        POST https://graph.facebook.com/{META_GRAPH_VERSION}/oauth/access_token
        Uses POST with application/x-www-form-urlencoded body so secrets never appear in URLs.
        """
        version = cls.get_version()
        url = f"{GRAPH_BASE}/{version}/oauth/access_token"
        data = {
            "client_id": settings.META_APP_ID or "",
            "client_secret": settings.META_APP_SECRET or "",
            "redirect_uri": settings.INSTAGRAM_REDIRECT_URI or "",
            "code": code,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, data=data)
            if resp.status_code != 200:
                err_info = cls._log_graph_error("exchange_code_for_user_token", resp)
                # Map specific error codes for safe user-facing redirects
                code_val = err_info.get("code")
                subcode_val = err_info.get("error_subcode")
                msg_val = (err_info.get("message") or "").lower()

                if code_val == 100 and ("redirect_uri" in msg_val or "mismatch" in msg_val):
                    raise ValueError("redirect_mismatch")
                elif code_val == 190 or subcode_val in (460, 463, 467) or "code has expired" in msg_val or "code has been used" in msg_val:
                    raise ValueError("code_used_or_expired")
                elif code_val in (1, 2, 4) and "secret" in msg_val:
                    raise ValueError("invalid_secret")
                else:
                    raise ValueError("token_exchange_failed")

            body = resp.json()
            return body["access_token"]

    @classmethod
    async def exchange_for_long_lived_user_token(cls, short_token: str) -> Tuple[str, int]:
        """
        Exchanges short-lived user token for a long-lived user token (~60 days).
        POST https://graph.facebook.com/{META_GRAPH_VERSION}/oauth/access_token
        Uses POST with application/x-www-form-urlencoded body so secrets and tokens never appear in URLs.
        """
        version = cls.get_version()
        url = f"{GRAPH_BASE}/{version}/oauth/access_token"
        data = {
            "grant_type": "fb_exchange_token",
            "client_id": settings.META_APP_ID or "",
            "client_secret": settings.META_APP_SECRET or "",
            "fb_exchange_token": short_token,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, data=data)
            if resp.status_code != 200:
                cls._log_graph_error("exchange_for_long_lived_user_token", resp)
                return short_token, 3600
            body = resp.json()
            return body["access_token"], body.get("expires_in", 5184000)

    @classmethod
    async def fetch_page_and_instagram_business_account(cls, user_token: str) -> Dict[str, Any]:
        """
        Flow: GET /me/accounts?fields=id,name,access_token,instagram_business_account{id,username,profile_picture_url,followers_count,media_count}
        Returns the first connected Page with an instagram_business_account.
        """
        version = cls.get_version()
        url = f"{GRAPH_BASE}/{version}/me/accounts"
        params = {
            "fields": "id,name,access_token,instagram_business_account{id,username,profile_picture_url,followers_count,media_count}",
            "access_token": user_token,
        }

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                cls._log_graph_error("fetch_page_and_instagram_business_account", resp)
                raise ValueError("token_exchange_failed")

            data = resp.json()
            pages = data.get("data", [])
            for page in pages:
                ig_account = page.get("instagram_business_account")
                if ig_account and "id" in ig_account:
                    return {
                        "page_id": page["id"],
                        "page_name": page.get("name"),
                        "page_access_token": page["access_token"],  # Permanent Page token
                        "ig_user_id": str(ig_account["id"]),
                        "ig_username": ig_account.get("username"),
                        "profile_picture_url": ig_account.get("profile_picture_url"),
                        "followers_count": ig_account.get("followers_count"),
                        "media_count": ig_account.get("media_count"),
                    }

            raise ValueError("no_instagram_business_account_found")

    # ---------------------------------------------------------------------------
    # Media Queries using Page Token
    # ---------------------------------------------------------------------------

    @classmethod
    async def fetch_instagram_media(
        cls,
        ig_user_id: str,
        page_token: str,
        after: Optional[str] = None,
        limit: int = 25
    ) -> Dict[str, Any]:
        """
        Fetches user media via:
        GET https://graph.facebook.com/{version}/{ig_user_id}/media
        Fields: id,caption,media_type,media_url,thumbnail_url,permalink,timestamp,children{media_url,media_type}
        """
        version = cls.get_version()
        url = f"{GRAPH_BASE}/{version}/{ig_user_id}/media"
        params = {
            "fields": "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp,children{media_url,media_type}",
            "limit": min(limit, 50),
            "access_token": page_token,
        }
        if after:
            params["after"] = after

        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.get(url, params=params)
            if resp.status_code != 200:
                logger.error(f"Failed to fetch IG media: HTTP {resp.status_code}")
                return {"data": [], "paging": {"cursors": {"after": None}}}
            return resp.json()

    # ---------------------------------------------------------------------------
    # Webhook & Signed Request Cryptographic Verification
    # ---------------------------------------------------------------------------

    @classmethod
    def verify_hub_signature(cls, raw_body: bytes, signature_header: Optional[str]) -> bool:
        """
        Verifies X-Hub-Signature-256 header using META_APP_SECRET and hmac.compare_digest.
        """
        if not signature_header or not settings.META_APP_SECRET:
            return False

        parts = signature_header.split("=", 1)
        if len(parts) != 2 or parts[0] != "sha256":
            return False

        expected_sig = hmac.new(
            settings.META_APP_SECRET.encode("utf-8"),
            raw_body,
            hashlib.sha256
        ).hexdigest()

        return hmac.compare_digest(expected_sig, parts[1])

    @classmethod
    def parse_signed_request(cls, signed_request: str) -> Optional[Dict[str, Any]]:
        """
        Parses Meta signed_request: <encoded_sig>.<payload>
        Validates HMAC-SHA256 signature against META_APP_SECRET.
        """
        if not signed_request or not settings.META_APP_SECRET or "." not in signed_request:
            return None

        try:
            encoded_sig, payload = signed_request.split(".", 1)

            # Pad base64url
            def b64url_decode(s: str) -> bytes:
                s += "=" * ((4 - len(s) % 4) % 4)
                return base64.urlsafe_b64decode(s)

            sig = b64url_decode(encoded_sig)
            data_bytes = b64url_decode(payload)
            data = json.loads(data_bytes.decode("utf-8"))

            algorithm = data.get("algorithm", "").upper()
            if algorithm != "HMAC-SHA256":
                return None

            expected_sig = hmac.new(
                settings.META_APP_SECRET.encode("utf-8"),
                payload.encode("utf-8"),
                hashlib.sha256
            ).digest()

            if not hmac.compare_digest(expected_sig, sig):
                return None

            return data
        except Exception as e:
            logger.warning(f"Failed to parse signed_request: {e}")
            return None

    # ---------------------------------------------------------------------------
    # Token Inspection & Refresh (Daily Validator Task)
    # ---------------------------------------------------------------------------

    @classmethod
    async def inspect_token(cls, access_token: str) -> Dict[str, Any]:
        """
        Inspects token validity via debug_token endpoint.
        Uses POST with body to prevent query string logging.
        """
        version = cls.get_version()
        url = f"{GRAPH_BASE}/{version}/debug_token"
        app_token = f"{settings.META_APP_ID}|{settings.META_APP_SECRET}"
        data = {
            "input_token": access_token,
            "access_token": app_token
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(url, data=data)
            if resp.status_code == 200:
                return resp.json().get("data", {})
            return {"is_valid": False}

    # ---------------------------------------------------------------------------
    # Multi-path Instagram Account Resolution (Task 1 & 2)
    # ---------------------------------------------------------------------------

    @classmethod
    async def _verify_instagram_account_candidate(
        cls,
        ig_user_id: str,
        token_to_verify: str,
        client: httpx.AsyncClient
    ) -> Optional[Dict[str, Any]]:
        """
        Calls GET /{ig_id}?fields=id,username,profile_picture_url,followers_count,media_count
        using the token to verify it can read Instagram metadata.
        """
        version = cls.get_version()
        url = f"{GRAPH_BASE}/{version}/{ig_user_id}"
        params = {
            "fields": "id,username,profile_picture_url,followers_count,media_count",
            "access_token": token_to_verify,
        }
        try:
            resp = await client.get(url, params=params)
            if resp.status_code == 200:
                data = resp.json()
                if "id" in data and "username" in data:
                    return {
                        "ig_user_id": str(data["id"]),
                        "ig_username": data["username"],
                        "profile_picture_url": data.get("profile_picture_url"),
                        "followers_count": data.get("followers_count"),
                        "media_count": data.get("media_count"),
                    }
            else:
                cls._log_graph_error(f"verify_ig_candidate_{ig_user_id}", resp)
        except Exception:
            pass
        return None

    @classmethod
    async def resolve_instagram_account(cls, user_token: str) -> Dict[str, Any]:
        """
        Resolves the target Instagram account across three distinct paths:
          Path A: debug_token granular_scopes -> target_ids (Facebook Login for Business)
          Path B: /me/accounts -> instagram_business_account (Classic Page-linked setups)
          Path C: /me/businesses -> instagram_accounts / owned_instagram_accounts (Business manager assets)

        Logs ONLY path name on success, and safe counts on failure.
        Never logs tokens, secrets, or URLs with query strings.
        Returns dictionary with account metadata + access_token + token_type ('user' or 'page').
        """
        version = cls.get_version()
        granular_scopes_count = 0
        pages_count = 0
        businesses_count = 0

        async with httpx.AsyncClient(timeout=15.0) as client:
            # -------------------------------------------------------------------
            # Path A: debug_token granular_scopes
            # -------------------------------------------------------------------
            debug_url = f"{GRAPH_BASE}/{version}/debug_token"
            app_token = f"{settings.META_APP_ID}|{settings.META_APP_SECRET}"
            debug_data = {
                "input_token": user_token,
                "access_token": app_token,
            }

            candidate_ids_a: List[str] = []
            try:
                debug_resp = await client.post(debug_url, data=debug_data)
                if debug_resp.status_code == 200:
                    d_json = debug_resp.json().get("data", {})
                    granular_scopes = d_json.get("granular_scopes", [])
                    granular_scopes_count = len(granular_scopes)

                    for g_scope in granular_scopes:
                        scope_name = g_scope.get("scope", "")
                        if scope_name.startswith("instagram_"):
                            target_ids = g_scope.get("target_ids", [])
                            for tid in target_ids:
                                tid_str = str(tid)
                                if tid_str not in candidate_ids_a:
                                    candidate_ids_a.append(tid_str)
            except Exception:
                pass

            for cid in candidate_ids_a:
                verified = await cls._verify_instagram_account_candidate(cid, user_token, client)
                if verified:
                    logger.info("Instagram account resolved via path: granular_scopes")
                    verified["access_token"] = user_token
                    verified["token_type"] = "user"
                    verified["page_id"] = None
                    verified["page_name"] = None
                    return verified

            # -------------------------------------------------------------------
            # Path B: /me/accounts (Classic Page-linked setups)
            # -------------------------------------------------------------------
            accounts_url = f"{GRAPH_BASE}/{version}/me/accounts"
            accounts_params = {
                "fields": "id,name,access_token,instagram_business_account{id,username,profile_picture_url,followers_count,media_count}",
                "access_token": user_token,
            }
            try:
                acc_resp = await client.get(accounts_url, params=accounts_params)
                if acc_resp.status_code == 200:
                    pages = acc_resp.json().get("data", [])
                    pages_count = len(pages)
                    for page in pages:
                        ig_acc = page.get("instagram_business_account")
                        if ig_acc and "id" in ig_acc:
                            page_token = page.get("access_token")
                            ig_id = str(ig_acc["id"])

                            # Test whether user token or page token works
                            token_to_use = user_token
                            token_type = "user"
                            verified = await cls._verify_instagram_account_candidate(ig_id, user_token, client)
                            if not verified and page_token:
                                verified = await cls._verify_instagram_account_candidate(ig_id, page_token, client)
                                if verified:
                                    token_to_use = page_token
                                    token_type = "page"

                            if verified:
                                logger.info("Instagram account resolved via path: me_accounts")
                                verified["access_token"] = token_to_use
                                verified["token_type"] = token_type
                                verified["page_id"] = page.get("id")
                                verified["page_name"] = page.get("name")
                                return verified
            except Exception:
                pass

            # -------------------------------------------------------------------
            # Path C: /me/businesses -> instagram_accounts / owned_instagram_accounts
            # -------------------------------------------------------------------
            biz_url = f"{GRAPH_BASE}/{version}/me/businesses"
            biz_params = {
                "fields": "id,name,instagram_accounts{id,username,profile_picture_url,followers_count,media_count},owned_instagram_accounts{id,username,profile_picture_url,followers_count,media_count}",
                "access_token": user_token,
            }
            try:
                biz_resp = await client.get(biz_url, params=biz_params)
                if biz_resp.status_code == 200:
                    businesses = biz_resp.json().get("data", [])
                    businesses_count = len(businesses)
                    for biz in businesses:
                        ig_list = (
                            biz.get("instagram_accounts", {}).get("data", [])
                            + biz.get("owned_instagram_accounts", {}).get("data", [])
                        )
                        for item in ig_list:
                            if "id" in item:
                                ig_id = str(item["id"])
                                verified = await cls._verify_instagram_account_candidate(ig_id, user_token, client)
                                if verified:
                                    logger.info("Instagram account resolved via path: me_businesses")
                                    verified["access_token"] = user_token
                                    verified["token_type"] = "user"
                                    verified["page_id"] = biz.get("id")
                                    verified["page_name"] = biz.get("name")
                                    return verified
            except Exception:
                pass

        # If none of the paths yielded a verified Instagram account:
        logger.warning(
            f"No Instagram account candidate found across paths: "
            f"granular_scopes_count={granular_scopes_count}, "
            f"pages_count={pages_count}, "
            f"businesses_count={businesses_count}"
        )
        raise ValueError("no_instagram")
