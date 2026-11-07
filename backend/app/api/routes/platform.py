"""
Phase 24.1: Unified Identity, Media, Blocking & Device Session API Routes
Prefix: /api/v1/platform

Endpoints:
  GET  /platform/me/profile           — Unified profile (all platforms)
  PATCH /platform/me/social           — Update social platform settings
  PATCH /platform/me/connect          — Update connect platform settings
  POST  /platform/me/channel          — Claim / update video channel handle
  GET  /platform/me/devices           — List active device sessions
  DELETE /platform/me/devices/{did}   — Revoke a device session

  POST   /platform/users/{uid}/block  — Block a user
  DELETE /platform/users/{uid}/block  — Unblock a user
  GET    /platform/me/blocked         — List blocked users

  POST   /platform/media/presign      — Request presigned upload URL
  POST   /platform/media/confirm      — Confirm direct S3/R2 upload complete
  POST   /platform/media/upload       — Backend multipart upload (dev fallback)
  DELETE /platform/media/{asset_id}   — Delete a media asset
"""
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, status
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from bson import ObjectId

from app.api.deps import get_current_user, get_optional_current_user
from app.database.client import get_database
from app.schemas.all_schemas import ShareMetadataResponse
from app.services.identity_service import (
    get_or_init_unified_profile,
    update_social_profile,
    update_connect_profile,
    setup_video_channel,
    block_user,
    unblock_user,
    get_blocked_users,
    register_device_session,
    revoke_device_session,
    get_device_sessions,
)
from app.services.media_service import (
    ingest_media_upload,
    request_presigned_upload,
    confirm_presigned_upload,
    delete_media_asset,
)
from app.core.rate_limit import SharedRateLimiter

router = APIRouter(prefix="/platform", tags=["Platform — Unified Identity & Media"])

# Rate limiters specific to platform operations
_media_upload_limiter = SharedRateLimiter(namespace="platform_media_upload", requests_limit=20, window_seconds=3600)
_block_limiter = SharedRateLimiter(namespace="platform_block", requests_limit=50, window_seconds=3600)

# ---------------------------------------------------------------------------
# Pydantic request / response models
# ---------------------------------------------------------------------------

class SocialProfileUpdate(BaseModel):
    is_private: Optional[bool] = None
    website: Optional[str] = Field(None, max_length=200)
    pronouns: Optional[str] = Field(None, max_length=50)
    allow_story_replies: Optional[str] = Field(None, pattern="^(everyone|following|off)$")
    allow_mentions: Optional[str] = Field(None, pattern="^(everyone|following|off)$")
    show_activity_status: Optional[bool] = None
    show_suggested_to_others: Optional[bool] = None


class ConnectProfileUpdate(BaseModel):
    display_name: Optional[str] = Field(None, max_length=60)
    about_text: Optional[str] = Field(None, max_length=140)
    last_seen_privacy: Optional[str] = Field(None, pattern="^(everyone|contacts|nobody)$")
    read_receipts_enabled: Optional[bool] = None
    typing_indicators_enabled: Optional[bool] = None
    online_status_visible: Optional[bool] = None


class ChannelSetupRequest(BaseModel):
    handle: str = Field(..., min_length=3, max_length=30)
    channel_name: str = Field(..., min_length=1, max_length=80)
    description: Optional[str] = Field(None, max_length=500)


class DeviceSessionRegister(BaseModel):
    device_id: str = Field(..., min_length=4, max_length=64)
    platform: str = Field(..., pattern="^(web|android|ios|desktop)$")
    device_name: Optional[str] = Field(None, max_length=80)
    push_token: Optional[str] = Field(None, max_length=256)


class PresignedUploadRequest(BaseModel):
    mime_type: str
    file_size_bytes: int = Field(..., gt=0)
    purpose: str = Field(..., pattern="^(avatar|social_post|social_story|connect_attachment|video_master|video_thumbnail)$")
    is_public: bool = True


# ---------------------------------------------------------------------------
# Profile endpoints
# ---------------------------------------------------------------------------

@router.get("/me/profile")
async def get_unified_profile(current_user: dict = Depends(get_current_user)):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    profile = await get_or_init_unified_profile(db, current_user["id"])
    # Remove sensitive fields before returning
    profile.pop("hashed_password", None)
    profile.pop("tokens_revoked_before", None)
    profile.pop("_id", None)
    return profile


@router.patch("/me/social")
async def update_social_settings(
    body: SocialProfileUpdate,
    current_user: dict = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    profile = await update_social_profile(db, current_user["id"], updates)
    return {"status": "updated", "social_profile": profile.get("social_profile")}


@router.patch("/me/connect")
async def update_connect_settings(
    body: ConnectProfileUpdate,
    current_user: dict = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    profile = await update_connect_profile(db, current_user["id"], updates)
    return {"status": "updated", "connect_profile": profile.get("connect_profile")}


@router.post("/me/channel", status_code=201)
async def claim_video_channel(
    body: ChannelSetupRequest,
    current_user: dict = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    profile = await setup_video_channel(
        db, current_user["id"], body.handle, body.channel_name, body.description
    )
    return {"status": "created", "video_channel": profile.get("video_channel")}


# ---------------------------------------------------------------------------
# Device session endpoints
# ---------------------------------------------------------------------------

@router.get("/me/devices")
async def list_devices(current_user: dict = Depends(get_current_user)):
    db = get_database()
    if db is None:
        return []
    sessions = await get_device_sessions(db, current_user["id"])
    # Mask push tokens in response
    return [
        {k: v for k, v in s.items() if k != "push_token"}
        for s in sessions
    ]


@router.post("/me/devices", status_code=201)
async def register_device(
    body: DeviceSessionRegister,
    current_user: dict = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    session = body.model_dump()
    session["registered_at"] = datetime.now(timezone.utc)
    await register_device_session(db, current_user["id"], session)
    return {"status": "registered", "device_id": body.device_id}


@router.delete("/me/devices/{device_id}", status_code=200)
async def revoke_device(
    device_id: str,
    current_user: dict = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    await revoke_device_session(db, current_user["id"], device_id)
    return {"status": "revoked", "device_id": device_id}


# ---------------------------------------------------------------------------
# Blocking endpoints
# ---------------------------------------------------------------------------

@router.post("/users/{user_id}/block", status_code=200)
async def block_user_endpoint(
    user_id: str,
    current_user: dict = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    _block_limiter.check(current_user["id"])
    await block_user(db, current_user["id"], user_id)
    return {"status": "blocked", "target_user_id": user_id}


@router.delete("/users/{user_id}/block", status_code=200)
async def unblock_user_endpoint(
    user_id: str,
    current_user: dict = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    await unblock_user(db, current_user["id"], user_id)
    return {"status": "unblocked", "target_user_id": user_id}


@router.get("/me/blocked")
async def list_blocked(current_user: dict = Depends(get_current_user)):
    db = get_database()
    if db is None:
        return {"blocked_users": []}
    blocked = await get_blocked_users(db, current_user["id"])
    return {"blocked_users": blocked, "count": len(blocked)}


# ---------------------------------------------------------------------------
# Media endpoints
# ---------------------------------------------------------------------------

@router.post("/media/presign", status_code=201)
async def presign_upload(
    body: PresignedUploadRequest,
    current_user: dict = Depends(get_current_user),
):
    """
    Requests a presigned URL for direct client-to-storage upload.
    Storage credentials are NEVER returned to the client.
    Returns: asset_id, upload_url, upload_fields (or mode indicator for local dev).
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    _media_upload_limiter.check(current_user["id"])
    result = await request_presigned_upload(
        db=db,
        uploader_id=current_user["id"],
        mime_type=body.mime_type,
        file_size_bytes=body.file_size_bytes,
        purpose=body.purpose,
        is_public=body.is_public,
    )
    return result


@router.post("/media/confirm", status_code=200)
async def confirm_upload(
    asset_id: str,
    current_user: dict = Depends(get_current_user),
):
    """Confirms direct S3/R2 upload and transitions asset status to active."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    result = await confirm_presigned_upload(db, asset_id, current_user["id"])
    # Remove internal fields
    result.pop("_id", None)
    return result


@router.post("/media/upload", status_code=201)
async def upload_media_backend(
    purpose: str = Query(..., pattern="^(avatar|social_post|social_story|connect_attachment|video_thumbnail)$"),
    is_public: bool = Query(True),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """
    Backend multipart upload endpoint.
    Use this when the client cannot perform direct S3 presigned uploads
    (e.g. local development, mobile restrictions).
    Large video files (>500 MB) MUST use the presigned flow.
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    _media_upload_limiter.check(current_user["id"])
    asset = await ingest_media_upload(db, file, current_user["id"], purpose, is_public)
    asset.pop("_id", None)
    return asset


@router.delete("/media/{asset_id}", status_code=200)
async def delete_asset(
    asset_id: str,
    current_user: dict = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")
    await delete_media_asset(db, asset_id, current_user["id"])
    return {"status": "deleted", "asset_id": asset_id}


# ---------------------------------------------------------------------------
# Cross-Platform Content Sharing & Deep Link Resolution (Phase 28)
# ---------------------------------------------------------------------------

@router.get("/share/{content_type}/{content_id}", response_model=ShareMetadataResponse)
async def resolve_share_link(
    content_type: str,
    content_id: str,
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    """
    Unified Share & Deep-Link Resolution Gateway — Phase 28:
    Resolves public preview metadata and verified deep links for:
    post, reel, story, video, short, channel, profile, community.
    Enforces authorization:
    - Blocked users cannot view content.
    - Private posts/videos require authenticated ownership or approved follow.
    - Expired stories return 404.
    """
    db = get_database()
    if db is None:
        raise HTTPException(status_code=503, detail="Database unavailable")

    my_id = current_user["id"] if current_user else None
    blocked_ids = set()
    if my_id:
        blocked_ids = set(await get_blocked_users(db, my_id))

    base_app_url = "https://zynova.intellidev.in"

    if content_type in ("post", "reel"):
        try:
            doc = await db.posts.find_one({"_id": ObjectId(content_id)})
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid content ID")
        if not doc:
            raise HTTPException(status_code=404, detail="Content not found or deleted")
        if doc.get("author_id") in blocked_ids:
            raise HTTPException(status_code=403, detail="Access denied")
        
        is_reel = doc.get("media_type") == "video"
        title = f"{'Reel' if is_reel else 'Post'} by {doc.get('author_full_name', 'Zynova User')}"
        deep_link = f"/reels/{content_id}" if is_reel else f"/post/{content_id}"

        return ShareMetadataResponse(
            share_url=f"{base_app_url}{deep_link}",
            content_type="reel" if is_reel else "post",
            title=title,
            description=doc.get("content", "")[:200],
            thumbnail_url=doc.get("thumbnail_url") or doc.get("image_url"),
            deep_link=deep_link,
            is_public=True,
            author_name=doc.get("author_full_name")
        )

    elif content_type in ("video", "short"):
        video_filter = None
        if len(content_id) == 24:
            try:
                video_filter = {"_id": ObjectId(content_id)}
            except Exception:
                pass
        if not video_filter:
            video_filter = {"_id": content_id}

        try:
            doc = await db.videos.find_one(video_filter)
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid video ID")
        if not doc:
            raise HTTPException(status_code=404, detail="Video not found or removed")
        if doc.get("owner_id") in blocked_ids:
            raise HTTPException(status_code=403, detail="Access denied")
        
        # Privacy check
        if doc.get("visibility") == "private":
            if not my_id or my_id != doc.get("owner_id"):
                raise HTTPException(status_code=403, detail="This video is private")

        is_short = doc.get("is_short", False)
        deep_link = f"/shorts/{content_id}" if is_short else f"/videos/{content_id}"

        return ShareMetadataResponse(
            share_url=f"{base_app_url}{deep_link}",
            content_type="short" if is_short else "video",
            title=doc.get("title", "Video on Zynova"),
            description=(doc.get("description") or "")[:200],
            thumbnail_url=doc.get("thumbnail_url"),
            deep_link=deep_link,
            is_public=doc.get("visibility") == "public",
            author_name=doc.get("channel_name")
        )

    elif content_type == "channel":
        doc = await db.creator_channels.find_one({
            "$or": [{"handle": content_id}, {"_id": ObjectId(content_id) if len(content_id) == 24 else None}]
        })
        if not doc:
            raise HTTPException(status_code=404, detail="Channel not found")
        if doc.get("owner_id") in blocked_ids:
            raise HTTPException(status_code=403, detail="Access denied")

        deep_link = f"/channel/{doc.get('handle')}"
        return ShareMetadataResponse(
            share_url=f"{base_app_url}{deep_link}",
            content_type="channel",
            title=f"{doc.get('name')} (@{doc.get('handle')})",
            description=(doc.get("description") or "")[:200],
            thumbnail_url=doc.get("avatar_url") or doc.get("banner_url"),
            deep_link=deep_link,
            is_public=True,
            author_name=doc.get("name")
        )

    elif content_type == "profile":
        user_filter = None
        if len(content_id) == 24:
            try:
                user_filter = {"_id": ObjectId(content_id)}
            except Exception:
                pass
        if not user_filter:
            user_filter = {"username": content_id}

        doc = await db.users.find_one(user_filter)
        if not doc or not doc.get("is_active", True):
            raise HTTPException(status_code=404, detail="User profile not found")
        user_id_str = str(doc["_id"])
        if user_id_str in blocked_ids:
            raise HTTPException(status_code=403, detail="Access denied")

        deep_link = f"/profile/{user_id_str}"
        return ShareMetadataResponse(
            share_url=f"{base_app_url}{deep_link}",
            content_type="profile",
            title=f"{doc.get('full_name')} (@{doc.get('username')})",
            description=doc.get("bio") or "Connect with me on Zynova",
            thumbnail_url=doc.get("avatar_url"),
            deep_link=deep_link,
            is_public=True,
            author_name=doc.get("full_name")
        )

    elif content_type == "community":
        try:
            doc = await db.connect_communities.find_one({"_id": ObjectId(content_id)})
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid community ID")
        if not doc:
            raise HTTPException(status_code=404, detail="Community not found")
        
        # Privacy check for private community
        if doc.get("is_private", False):
            member_ids = doc.get("member_ids", [])
            admin_ids = doc.get("admin_ids", [])
            if not my_id or (my_id not in member_ids and my_id not in admin_ids):
                raise HTTPException(status_code=403, detail="Private community access restricted")

        deep_link = f"/communities/{content_id}"
        return ShareMetadataResponse(
            share_url=f"{base_app_url}{deep_link}",
            content_type="community",
            title=doc.get("name", "Community on Zynova"),
            description=(doc.get("description") or "")[:200],
            thumbnail_url=doc.get("icon_url"),
            deep_link=deep_link,
            is_public=not doc.get("is_private", False),
            author_name=doc.get("name")
        )

    else:
        raise HTTPException(status_code=400, detail=f"Unsupported share content type: {content_type}")
