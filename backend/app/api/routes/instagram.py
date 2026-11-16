import os
import json
import secrets
import html
import uuid
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status, BackgroundTasks
from fastapi.responses import RedirectResponse, PlainTextResponse
from pydantic import BaseModel, Field
from bson import ObjectId
import httpx
import aiofiles

from app.api.deps import get_current_user
from app.database.client import get_database
from app.core.config import settings
from app.core.rate_limit import check_instagram_rate_limit
from app.core.crypto_kms import encrypt_field, decrypt_field
from app.services.meta_instagram_service import MetaInstagramService
from app.services.social_service import extract_hashtags
from app.services.media_service import (
    get_storage_adapter,
    MIME_CONFIG,
    _validate_magic,
    _validate_mime,
    QUARANTINE_DIR,
    _safe_remove,
    CHUNK_SIZE
)

logger = logging.getLogger("zynova.instagram_routes")

router = APIRouter(prefix="/instagram", tags=["Instagram Integration"])


# ---------------------------------------------------------------------------
# Mobile Contract Pydantic Models (Matching EXACT mobile contract)
# ---------------------------------------------------------------------------

class AuthorizeUrlResponse(BaseModel):
    url: str

class InstagramStatusResponse(BaseModel):
    connected: bool
    username: Optional[str] = None
    status: str = Field(..., pattern="^(active|needs_reconnect|not_connected)$")
    last_synced_at: Optional[str] = None
    media_count: Optional[int] = None

class MediaItem(BaseModel):
    id: str
    caption: Optional[str] = None
    media_type: str
    media_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    permalink: Optional[str] = None
    timestamp: Optional[str] = None
    already_imported: bool = False

class MediaCursors(BaseModel):
    after: Optional[str] = None

class MediaPaging(BaseModel):
    cursors: MediaCursors

class MediaListResponse(BaseModel):
    data: List[MediaItem]
    paging: MediaPaging

class ImportMediaRequest(BaseModel):
    media_ids: List[str] = Field(..., min_length=1, max_length=20)

class ImportItemResult(BaseModel):
    id: str
    status: str = Field(..., pattern="^(imported|skipped|failed)$")
    post_id: Optional[str] = None
    message: Optional[str] = None

class ImportResponse(BaseModel):
    results: List[ImportItemResult]

class DisconnectResponse(BaseModel):
    ok: bool = True

class DataDeletionResponse(BaseModel):
    url: str
    confirmation_code: str


# ---------------------------------------------------------------------------
# 1. GET /authorize-url?platform=web|android|ios
# ---------------------------------------------------------------------------

@router.get("/authorize-url", response_model=AuthorizeUrlResponse)
async def get_instagram_authorize_url(
    platform: str = Query("android", pattern="^(web|android|ios)$"),
    current_user: dict = Depends(get_current_user)
):
    """
    Returns the official Facebook OAuth dialog URL for Instagram Graph API.
    Generates a secure state token (secrets.token_urlsafe(32)), stores it in Redis (TTL 600s).
    State does NOT expose user_id.
    """
    check_instagram_rate_limit(f"auth_url:{current_user['id']}")

    if not MetaInstagramService.is_configured():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Meta/Instagram integration credentials not configured on backend."
        )

    # 32-byte cryptographically secure random state (no user ID in string)
    state = secrets.token_urlsafe(32)

    # Store state in Redis with 600s TTL
    await MetaInstagramService.store_state(
        state=state,
        user_id=current_user["id"],
        platform=platform
    )

    url = MetaInstagramService.get_oauth_dialog_url(state=state)
    return AuthorizeUrlResponse(url=url)


# ---------------------------------------------------------------------------
# 2. GET /callback (Public OAuth redirect handler)
# ---------------------------------------------------------------------------

@router.get("/callback")
async def instagram_oauth_callback(
    code: Optional[str] = Query(None),
    error: Optional[str] = Query(None),
    error_reason: Optional[str] = Query(None),
    error_description: Optional[str] = Query(None),
    state: Optional[str] = Query(None),
):
    """
    Public OAuth Callback.
    Atomically retrieves and deletes state from Redis.
    Exchanges code for Page token, encrypts token with crypto_kms, and stores connection.
    Redirects to:
      - Mobile: zenova://oauth/instagram?status=success&username=<u> or ?status=error&error=<code>&error_description=<text>
      - Web: {WEB_APP_URL}/settings/connections?ig=success or ?ig=error&error=<code>
    """
    check_instagram_rate_limit("ig_callback")
    db = get_database()

    def make_redirect(platform: str, is_success: bool, username: Optional[str] = None, err_code: Optional[str] = None, err_desc: Optional[str] = None):
        scheme = settings.MOBILE_DEEP_LINK_SCHEME or "zenova"
        web_base = settings.WEB_APP_URL.rstrip("/")

        if platform == "web":
            if is_success:
                return f"{web_base}/settings/connections?ig=success"
            return f"{web_base}/settings/connections?ig=error&error={err_code or 'oauth_error'}"
        else:
            if is_success:
                return f"{scheme}://oauth/instagram?status=success&username={username or ''}"
            desc_part = f"&error_description={err_desc}" if err_desc else ""
            return f"{scheme}://oauth/instagram?status=error&error={err_code or 'oauth_error'}{desc_part}"

    # Verify if user rejected
    if error or not code:
        err = error or error_reason or "access_denied"
        desc = error_description or "User cancelled or denied authorization"
        platform = "android"
        if state:
            st = await MetaInstagramService.get_and_delete_state(state)
            if st:
                platform = st.get("platform", "android")
        return RedirectResponse(url=make_redirect(platform, False, err_code=err, err_desc=desc), status_code=302)

    if not state:
        return RedirectResponse(url=make_redirect("android", False, err_code="missing_state"), status_code=302)

    # Atomic get + delete from Redis
    state_data = await MetaInstagramService.get_and_delete_state(state)
    if not state_data:
        return RedirectResponse(url=make_redirect("android", False, err_code="state_invalid_or_expired"), status_code=302)

    user_id = state_data["user_id"]
    platform = state_data.get("platform", "android")

    if db is None:
        return RedirectResponse(url=make_redirect(platform, False, err_code="database_unavailable"), status_code=302)

    try:
        # Step 1: Exchange code for short-lived user access token
        short_user_token = await MetaInstagramService.exchange_code_for_user_token(code)

        # Step 2: Exchange for long-lived user access token (60 days)
        long_user_token, expires_in = await MetaInstagramService.exchange_for_long_lived_user_token(short_user_token)

        # Step 3: Multi-path resolution (granular_scopes -> /me/accounts -> /me/businesses)
        account_info = await MetaInstagramService.resolve_instagram_account(long_user_token)

        page_id = account_info.get("page_id")
        token_to_store = account_info["access_token"]
        token_type = account_info.get("token_type", "user")
        ig_user_id = account_info["ig_user_id"]
        ig_username = account_info["ig_username"]
        media_count = account_info.get("media_count", 0)

        # Step 4: Encrypt access token with crypto_kms envelope encryption
        access_token_enc = encrypt_field(token_to_store, context=f"ig_token:{user_id}")

        now = datetime.now(timezone.utc)
        token_expires_at = now + timedelta(seconds=expires_in)

        # Step 5: Upsert connection into instagram_connections collection
        doc = {
            "user_id": user_id,
            "ig_user_id": ig_user_id,
            "ig_username": ig_username,
            "page_id": page_id,
            "access_token_enc": access_token_enc,
            "token_type": token_type,
            "token_expires_at": token_expires_at,
            "status": "active",
            "connected_at": now,
            "last_synced_at": now,
            "media_count": media_count
        }

        await db.instagram_connections.update_one(
            {"user_id": user_id},
            {"$set": doc},
            upsert=True
        )

        # Update user social profile flags
        try:
            await db.users.update_one(
                {"_id": ObjectId(user_id)},
                {
                    "$set": {
                        "social_profile.instagram_connected": True,
                        "social_profile.instagram_username": ig_username,
                        "social_profile.instagram_user_id": ig_user_id
                    }
                }
            )
        except Exception:
            pass

        return RedirectResponse(url=make_redirect(platform, True, username=ig_username), status_code=302)

    except ValueError as ve:
        err_msg = str(ve)
        logger.warning(f"Instagram business account error: {err_msg}")
        return RedirectResponse(url=make_redirect(platform, False, err_code=err_msg), status_code=302)
    except Exception as e:
        logger.error(f"Error completing Meta Instagram OAuth: {e}")
        return RedirectResponse(url=make_redirect(platform, False, err_code="token_exchange_failed"), status_code=302)


# ---------------------------------------------------------------------------
# 3. GET /status
# ---------------------------------------------------------------------------

@router.get("/status", response_model=InstagramStatusResponse)
async def get_instagram_status(current_user: dict = Depends(get_current_user)):
    """
    Returns connection status:
    { "connected": bool, "username": string|null, "status": "active"|"needs_reconnect"|"not_connected", "last_synced_at": ISO|null, "media_count": number|null }
    """
    check_instagram_rate_limit(f"status:{current_user['id']}")
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    conn = await db.instagram_connections.find_one({"user_id": current_user["id"]})
    if not conn:
        return InstagramStatusResponse(
            connected=False,
            username=None,
            status="not_connected",
            last_synced_at=None,
            media_count=None
        )

    last_sync = conn["last_synced_at"].isoformat() if isinstance(conn.get("last_synced_at"), datetime) else None

    # Check expiration
    conn_status = conn.get("status", "active")
    if conn.get("token_expires_at"):
        if datetime.now(timezone.utc) >= conn["token_expires_at"]:
            conn_status = "needs_reconnect"

    return InstagramStatusResponse(
        connected=True,
        username=conn.get("ig_username"),
        status=conn_status,
        last_synced_at=last_sync,
        media_count=conn.get("media_count")
    )


# ---------------------------------------------------------------------------
# 4. GET /media?after=
# ---------------------------------------------------------------------------

@router.get("/media", response_model=MediaListResponse)
async def get_instagram_media(
    after: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    """
    Returns user media from Instagram Graph API using decrypted Page access token.
    Flags each item with already_imported: bool if already in posts collection.
    """
    check_instagram_rate_limit(f"media:{current_user['id']}")
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    conn = await db.instagram_connections.find_one({"user_id": current_user["id"]})
    if not conn or not conn.get("access_token_enc"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Instagram not connected")

    # Decrypt stored token with crypto_kms (supports backward compatibility with ig_page_token context)
    enc_token = conn["access_token_enc"]
    try:
        active_token = decrypt_field(enc_token, context=f"ig_token:{current_user['id']}")
    except Exception:
        active_token = decrypt_field(enc_token, context=f"ig_page_token:{current_user['id']}")

    ig_user_id = conn["ig_user_id"]

    raw_data = await MetaInstagramService.fetch_instagram_media(
        ig_user_id=ig_user_id,
        page_token=active_token,
        after=after,
        limit=25
    )

    items = raw_data.get("data", [])
    paging_cursor = raw_data.get("paging", {}).get("cursors", {}).get("after")

    # Find already imported media IDs for this user
    media_ids = [item["id"] for item in items if "id" in item]
    imported_set = set()
    if media_ids:
        cursor = db.posts.find(
            {"author_id": current_user["id"], "instagram_media_id": {"$in": media_ids}},
            {"instagram_media_id": 1}
        )
        async for doc in cursor:
            if doc.get("instagram_media_id"):
                imported_set.add(doc["instagram_media_id"])

    result_items: List[MediaItem] = []
    for item in items:
        m_id = item["id"]
        # Handle media_url for CAROUSEL_ALBUM if top-level missing
        media_url = item.get("media_url")
        if not media_url and item.get("children", {}).get("data"):
            media_url = item["children"]["data"][0].get("media_url")

        result_items.append(MediaItem(
            id=m_id,
            caption=item.get("caption"),
            media_type=item.get("media_type", "IMAGE"),
            media_url=media_url,
            thumbnail_url=item.get("thumbnail_url"),
            permalink=item.get("permalink"),
            timestamp=item.get("timestamp"),
            already_imported=(m_id in imported_set)
        ))

    # Update last_synced_at
    await db.instagram_connections.update_one(
        {"user_id": current_user["id"]},
        {"$set": {"last_synced_at": datetime.now(timezone.utc)}}
    )

    return MediaListResponse(
        data=result_items,
        paging=MediaPaging(cursors=MediaCursors(after=paging_cursor))
    )


# ---------------------------------------------------------------------------
# 5. POST /import { "media_ids": [] } (Max 20)
# ---------------------------------------------------------------------------

@router.post("/import", response_model=ImportResponse)
async def import_instagram_media(
    payload: ImportMediaRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Imports up to 20 media items from Instagram:
      - Skips duplicate imports (unique sparse index on user_id + instagram_media_id)
      - Downloads media with httpx (15s timeout, size cap, MIME allowlist)
      - Re-hosts to Cloudflare R2 / S3 via media_service (zero permanent local disk storage)
      - Validates and creates post via same standard as POST /social/posts:
          html.escape content, hashtags extraction, author stats incremented
      - Adds source="instagram", instagram_media_id, instagram_permalink
    """
    check_instagram_rate_limit(f"import:{current_user['id']}")
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    conn = await db.instagram_connections.find_one({"user_id": current_user["id"]})
    if not conn or not conn.get("access_token_enc"):
        raise HTTPException(status_code=400, detail="Instagram not connected")

    # Decrypt stored token with crypto_kms (supports backward compatibility with ig_page_token context)
    enc_token = conn["access_token_enc"]
    try:
        active_token = decrypt_field(enc_token, context=f"ig_token:{current_user['id']}")
    except Exception:
        active_token = decrypt_field(enc_token, context=f"ig_page_token:{current_user['id']}")

    storage_adapter = get_storage_adapter()
    version = MetaInstagramService.get_version()

    results: List[ImportItemResult] = []

    async with httpx.AsyncClient(timeout=15.0) as http_client:
        for media_id in payload.media_ids:
            # 1. Duplicate check
            existing = await db.posts.find_one({"author_id": current_user["id"], "instagram_media_id": media_id})
            if existing:
                results.append(ImportItemResult(
                    id=media_id,
                    status="skipped",
                    post_id=str(existing["_id"]),
                    message="Already imported"
                ))
                continue

            # 2. Fetch specific media metadata from Meta Graph
            meta_url = f"https://graph.facebook.com/{version}/{media_id}"
            meta_resp = await http_client.get(
                meta_url,
                params={
                    "fields": "id,caption,media_type,media_url,thumbnail_url,permalink,timestamp,children{media_url,media_type}",
                    "access_token": active_token
                }
            )

            if meta_resp.status_code != 200:
                results.append(ImportItemResult(
                    id=media_id,
                    status="failed",
                    message="Failed to fetch media details from Instagram"
                ))
                continue

            m_data = meta_resp.json()
            media_type_raw = m_data.get("media_type", "IMAGE")
            target_url = m_data.get("media_url")

            # Handle CAROUSEL_ALBUM
            if not target_url and m_data.get("children", {}).get("data"):
                target_url = m_data["children"]["data"][0].get("media_url")

            if not target_url:
                results.append(ImportItemResult(
                    id=media_id,
                    status="failed",
                    message="Media download URL unavailable"
                ))
                continue

            # 3. Stream download with size cap and MIME validation
            tmp_filename = f"ig_imp_{uuid.uuid4().hex}"
            tmp_path = os.path.join(QUARANTINE_DIR, tmp_filename)
            try:
                async with http_client.stream("GET", target_url) as stream_resp:
                    if stream_resp.status_code != 200:
                        raise ValueError(f"Download HTTP {stream_resp.status_code}")

                    declared_mime = stream_resp.headers.get("content-type", "").split(";")[0].strip().lower()
                    if not declared_mime or declared_mime not in MIME_CONFIG:
                        # Fallback based on media_type_raw
                        declared_mime = "video/mp4" if media_type_raw == "VIDEO" else "image/jpeg"

                    cfg = _validate_mime(declared_mime)
                    max_bytes = cfg["max_mb"] * 1024 * 1024
                    ext = cfg["ext"]

                    total_bytes = 0
                    header_checked = False

                    async with aiofiles.open(tmp_path, "wb") as f_out:
                        async for chunk in stream_resp.aiter_bytes(chunk_size=CHUNK_SIZE):
                            if not header_checked and chunk:
                                if not _validate_magic(chunk[:64], cfg["mime"]):
                                    raise ValueError("File magic signature mismatch")
                                header_checked = True

                            total_bytes += len(chunk)
                            if total_bytes > max_bytes:
                                raise ValueError("Media file size cap exceeded")

                            await f_out.write(chunk)

                # 4. Upload to Cloudflare R2 / S3 via storage adapter
                dest_key = f"social/instagram/{current_user['id'][:8]}/{uuid.uuid4().hex}{ext}"
                rehosted_url = await storage_adapter.save_file(
                    file_path=tmp_path,
                    destination_key=dest_key,
                    content_type=cfg["mime"],
                    is_public=True
                )

                # 5. Build post document
                raw_caption = m_data.get("caption") or ""
                escaped_content = html.escape(raw_caption.strip()) or "Instagram Import"
                tags = extract_hashtags(escaped_content)
                now = datetime.now(timezone.utc)
                media_category = "video" if cfg["category"] == "video" else "image"

                post_doc = {
                    "author_id": current_user["id"],
                    "author_username": current_user["username"],
                    "author_full_name": current_user["full_name"],
                    "author_avatar": current_user.get("avatar_url"),
                    "content": escaped_content,
                    "image_url": rehosted_url if media_category == "image" else None,
                    "media_url": rehosted_url,
                    "media_type": media_category,
                    "media_assets": [rehosted_url],
                    "tags": tags,
                    "source": "instagram",
                    "instagram_media_id": media_id,
                    "instagram_permalink": m_data.get("permalink"),
                    "likes": [],
                    "likes_count": 0,
                    "comments_count": 0,
                    "is_edited": False,
                    "created_at": now,
                    "updated_at": now
                }

                insert_res = await db.posts.insert_one(post_doc)
                new_post_id = str(insert_res.inserted_id)

                # Increment user posts_count
                await db.users.update_one({"_id": ObjectId(current_user["id"])}, {"$inc": {"posts_count": 1}})

                results.append(ImportItemResult(
                    id=media_id,
                    status="imported",
                    post_id=new_post_id,
                    message="Imported successfully"
                ))

            except Exception as imp_err:
                logger.error(f"Failed importing media {media_id}: {imp_err}")
                results.append(ImportItemResult(
                    id=media_id,
                    status="failed",
                    message=str(imp_err)
                ))
            finally:
                _safe_remove(tmp_path)

    return ImportResponse(results=results)


# ---------------------------------------------------------------------------
# 6. DELETE /disconnect
# ---------------------------------------------------------------------------

@router.delete("/disconnect", response_model=DisconnectResponse)
async def disconnect_instagram_account(current_user: dict = Depends(get_current_user)):
    """
    Disconnects Instagram account and clears credentials.
    """
    check_instagram_rate_limit(f"disconnect:{current_user['id']}")
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    await db.instagram_connections.delete_many({"user_id": current_user["id"]})

    try:
        await db.users.update_one(
            {"_id": ObjectId(current_user["id"])},
            {
                "$set": {
                    "social_profile.instagram_connected": False,
                    "social_profile.instagram_username": None,
                    "social_profile.instagram_user_id": None
                }
            }
        )
    except Exception:
        pass

    return DisconnectResponse(ok=True)


# ---------------------------------------------------------------------------
# 7. POST /refresh (Manual Token Refresh)
# ---------------------------------------------------------------------------

@router.post("/refresh")
async def refresh_instagram_token(current_user: dict = Depends(get_current_user)):
    """
    Validates and updates the stored Instagram connection.
    """
    check_instagram_rate_limit(f"refresh:{current_user['id']}")
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    conn = await db.instagram_connections.find_one({"user_id": current_user["id"]})
    if not conn:
        raise HTTPException(status_code=404, detail="Instagram connection not found")

    # Decrypt stored token with crypto_kms (supports backward compatibility with ig_page_token context)
    enc_token = conn["access_token_enc"]
    try:
        active_token = decrypt_field(enc_token, context=f"ig_token:{current_user['id']}")
    except Exception:
        active_token = decrypt_field(enc_token, context=f"ig_page_token:{current_user['id']}")

    inspection = await MetaInstagramService.inspect_token(active_token)

    if not inspection.get("is_valid", False):
        await db.instagram_connections.update_one(
            {"user_id": current_user["id"]},
            {"$set": {"status": "needs_reconnect"}}
        )
        return {"status": "needs_reconnect", "is_valid": False}

    await db.instagram_connections.update_one(
        {"user_id": current_user["id"]},
        {"$set": {"status": "active", "last_synced_at": datetime.now(timezone.utc)}}
    )
    return {"status": "active", "is_valid": True}


# ---------------------------------------------------------------------------
# 8. Webhook Endpoints: GET /webhook & POST /webhook
# ---------------------------------------------------------------------------

@router.get("/webhook")
async def verify_instagram_webhook(
    hub_mode: Optional[str] = Query(None, alias="hub.mode"),
    hub_verify_token: Optional[str] = Query(None, alias="hub.verify_token"),
    hub_challenge: Optional[str] = Query(None, alias="hub.challenge"),
):
    """
    Meta Webhook Verification (Challenge-Response):
    Returns hub.challenge as PlainTextResponse if hub.verify_token matches INSTAGRAM_WEBHOOK_VERIFY_TOKEN.
    """
    expected_token = settings.INSTAGRAM_WEBHOOK_VERIFY_TOKEN
    if hub_mode == "subscribe" and hub_verify_token and expected_token and hub_verify_token == expected_token:
        logger.info("Meta Webhook verification challenge accepted.")
        return PlainTextResponse(content=hub_challenge or "", status_code=200)

    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verification token mismatch")

@router.post("/webhook")
async def receive_instagram_webhook(
    request: Request,
    background_tasks: BackgroundTasks
):
    """
    Meta Webhook receiver:
    Verifies X-Hub-Signature-256 (HMAC-SHA256, META_APP_SECRET, raw body, hmac.compare_digest).
    Returns 200 Fast, offloading work to BackgroundTasks.
    """
    raw_body = await request.body()
    signature_header = request.headers.get("X-Hub-Signature-256")

    if not MetaInstagramService.verify_hub_signature(raw_body, signature_header):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid HMAC signature")

    try:
        payload = json.loads(raw_body.decode("utf-8"))
        async def process_webhook_events(data: dict):
            logger.info(f"Processing Meta webhook in background: {data.get('object')}")

        background_tasks.add_task(process_webhook_events, payload)
    except Exception as e:
        logger.warning(f"Error parsing webhook JSON: {e}")

    return {"status": "received"}


# ---------------------------------------------------------------------------
# 9. Meta Compliance: POST /deauthorize & POST /data-deletion
# ---------------------------------------------------------------------------

@router.post("/deauthorize")
async def meta_deauthorize_callback(request: Request):
    """
    Meta Deauthorization Callback:
    Triggered when a user removes the app from their Facebook/Instagram settings.
    Parses and verifies signed_request, sets status to 'needs_reconnect' or removes credentials.
    """
    form_data = await request.form()
    signed_req = form_data.get("signed_request")
    parsed = MetaInstagramService.parse_signed_request(signed_req or "")
    if not parsed:
        raise HTTPException(status_code=400, detail="Invalid signed_request signature")

    meta_user_id = parsed.get("user_id")
    if meta_user_id:
        db = get_database()
        if db is not None:
            await db.instagram_connections.update_one(
                {"page_id": meta_user_id},
                {"$set": {"status": "needs_reconnect"}}
            )

    return {"status": "deauthorized"}

@router.post("/data-deletion", response_model=DataDeletionResponse)
async def meta_data_deletion_callback(request: Request):
    """
    Meta User Data Deletion Callback:
    Triggered when a user requests data deletion via Facebook settings.
    Parses and verifies signed_request, deletes connection data,
    and returns { url: "{WEB_APP_URL}/data-deletion?code=<code>", confirmation_code }.
    """
    form_data = await request.form()
    signed_req = form_data.get("signed_request")
    parsed = MetaInstagramService.parse_signed_request(signed_req or "")
    if not parsed:
        raise HTTPException(status_code=400, detail="Invalid signed_request signature")

    confirmation_code = f"del_{secrets.token_hex(16)}"
    db = get_database()
    if db is not None:
        meta_user_id = parsed.get("user_id")
        if meta_user_id:
            await db.instagram_connections.delete_many({"page_id": meta_user_id})

        # Save confirmation code for public lookup
        await db.data_deletion_requests.insert_one({
            "confirmation_code": confirmation_code,
            "meta_user_id": meta_user_id,
            "status": "completed",
            "requested_at": datetime.now(timezone.utc)
        })

    web_base = settings.WEB_APP_URL.rstrip("/")
    status_url = f"{web_base}/data-deletion?code={confirmation_code}"

    return DataDeletionResponse(
        url=status_url,
        confirmation_code=confirmation_code
    )
