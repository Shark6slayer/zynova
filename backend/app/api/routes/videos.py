"""
Zynova Video API Routes (Phase 27 Extended + Phase 12.2 Gap Closure).
Exposes endpoints for:
- Creator channels (create, update, get by handle, subscriber counts, analytics).
- Sovereign YouTube Data API v3 proxy with `pageToken` cursor pagination, batch `videos.list` enrichment & `videoCategories.list`.
- Saved videos (`GET/POST/DELETE /videos/saved`) supporting Zenova & permitted YouTube metadata references.
- Playlists (`GET/POST /videos/playlists`, `GET/DELETE /videos/playlists/{id}`, add/remove items).
- Watch progress & history retrieval/deletion (`/videos/user/history`).
- Video & Shorts upload, R2/local Range streaming, signed stream URL, update, and deletion.
- Shorts continuous swipe-feed (`/videos/shorts`) & paginated discovery/recommendations (`/videos`, `/videos/recommendations`).
"""

import os
import re
import uuid
import aiofiles
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Set
from fastapi import (
    APIRouter, HTTPException, status, Depends, Query,
    UploadFile, File, Form, Request, Header
)
from fastapi.responses import StreamingResponse
from bson import ObjectId

from app.schemas.all_schemas import (
    ChannelCreatePayload,
    ChannelResponse,
    VideoResponse,
    VideoUpdate,
    VideoCommentCreate,
    VideoCommentResponse,
    PlaylistCreatePayload,
    PlaylistResponse,
    PlaylistDetailResponse,
    SaveVideoPayload,
    SavedVideoEntryResponse,
    YouTubeSavedMetadata,
    YouTubeSearchResponse,
    YouTubeShortsResponse,
    YouTubeCategoriesResponse,
    YouTubeVideoStatusResponse,
    VideoStreamUrlResponse,
    WatchProgressPayload,
    WatchHistoryResponse,
    CreatorAnalyticsResponse,
)
from app.database.client import get_database
from app.api.deps import get_current_user, get_optional_current_user
from app.core.rate_limit import check_video_upload_rate_limit, check_video_comment_rate_limit
from app.core.scanner import scan_quarantined_media, QUARANTINE_DIR
from app.services import video_service, youtube_service
from app.services.identity_service import get_blocked_users
from app.services.media_service import (
    get_storage_adapter,
    S3StorageAdapter,
    LocalDevStorageAdapter,
)

router = APIRouter(prefix="/videos", tags=["Zynova Video & Shorts Platform"])

STORAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "storage", "videos"))
os.makedirs(STORAGE_DIR, exist_ok=True)

MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100MB multipart limit
CHUNK_SIZE = 1024 * 1024            # 1MB chunk size
ALLOWED_MIME_TYPES = {
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/ogg": ".ogv",
    "video/quicktime": ".mov"
}

MAGIC_BYTES = {
    b"\x00\x00\x00\x18ftyp": "video/mp4",
    b"\x00\x00\x00\x20ftyp": "video/mp4",
    b"\x00\x00\x00\x1cftyp": "video/mp4",
    b"\x1a\x45\xdf\xa3": "video/webm",
    b"OggS": "video/ogg",
    b"\x00\x00\x00\x14ftypqt": "video/quicktime"
}

RANGE_HEADER_RE = re.compile(r"^bytes=(\d*)-(\d*)$")


def verify_video_magic_bytes(header_bytes: bytes) -> bool:
    if len(header_bytes) < 4:
        return False
    for magic in MAGIC_BYTES:
        if header_bytes.startswith(magic) or magic in header_bytes[:32]:
            return True
    return False


def build_video_response(
    v: dict,
    current_user_id: Optional[str] = None,
    saved_ids: Optional[Set[str]] = None,
) -> VideoResponse:
    likes_list = v.get("likes", [])
    dislikes_list = v.get("dislikes", [])
    vid_id = str(v["_id"])
    is_liked = (current_user_id in likes_list) if current_user_id else False
    is_owner = (current_user_id == v.get("owner_id")) if current_user_id else False
    is_saved = (vid_id in saved_ids) if saved_ids is not None else False

    return VideoResponse(
        id=vid_id,
        owner_id=v["owner_id"],
        owner_username=v.get("owner_username", ""),
        owner_full_name=v.get("owner_full_name", ""),
        owner_avatar=v.get("owner_avatar"),
        channel_id=v.get("channel_id"),
        channel_handle=v.get("channel_handle"),
        channel_name=v.get("channel_name"),
        title=v["title"],
        description=v.get("description"),
        storage_key=v["storage_key"],
        mime_type=v["mime_type"],
        file_size_bytes=v["file_size_bytes"],
        duration_seconds=v.get("duration_seconds"),
        thumbnail_url=v.get("thumbnail_url"),
        visibility=v.get("visibility", "public"),
        status=v.get("status", "published"),
        category=v.get("category", "General"),
        is_short=v.get("is_short", False),
        aspect_ratio=v.get("aspect_ratio", "16:9"),
        audio_title=v.get("audio_title"),
        audio_artist=v.get("audio_artist"),
        view_count=v.get("view_count", 0),
        likes_count=v.get("likes_count", len(likes_list)),
        dislikes_count=v.get("dislikes_count", len(dislikes_list)),
        comments_count=v.get("comments_count", 0),
        is_liked=is_liked,
        is_saved=is_saved,
        is_owner=is_owner,
        created_at=v["created_at"],
        updated_at=v.get("updated_at", v["created_at"])
    )


def _playlist_to_response(p: dict) -> PlaylistResponse:
    return PlaylistResponse(
        id=str(p["_id"]),
        owner_id=p["owner_id"],
        owner_username=p["owner_username"],
        title=p["title"],
        description=p.get("description"),
        visibility=p["visibility"],
        video_ids=p.get("video_ids", []),
        videos_count=p.get("videos_count", len(p.get("video_ids", []))),
        created_at=p["created_at"],
        updated_at=p["updated_at"],
    )


def _check_video_stream_access(video: dict, current_uid: Optional[str]) -> None:
    if video.get("is_deleted") or video.get("moderation_status") in ("removed", "rejected", "hidden"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    is_owner = bool(current_uid and current_uid == video.get("owner_id"))
    if video.get("status", "published") != "published" and not is_owner:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Video is not published yet")
    if video.get("visibility") == "private" and not is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Private video stream unauthorized: content is restricted to creator."
        )


def _parse_byte_range(range_header: Optional[str], file_size: int) -> tuple[int, int, bool]:
    """Parses RFC 9110 Range header and raises HTTP 416 on unsatisfiable bounds."""
    if not range_header:
        return 0, max(0, file_size - 1), False
    match = RANGE_HEADER_RE.match(range_header.strip())
    if not match:
        raise HTTPException(
            status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
            detail="Malformed Range header",
            headers={"Content-Range": f"bytes */{file_size}"},
        )
    start_str, end_str = match.group(1), match.group(2)
    if not start_str and not end_str:
        raise HTTPException(
            status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
            detail="Empty Range header",
            headers={"Content-Range": f"bytes */{file_size}"},
        )
    if not start_str:
        suffix_len = int(end_str)
        if suffix_len <= 0:
            raise HTTPException(
                status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
                detail="Invalid suffix range",
                headers={"Content-Range": f"bytes */{file_size}"},
            )
        start = max(0, file_size - suffix_len)
        end = file_size - 1
    else:
        start = int(start_str)
        end = int(end_str) if end_str else (file_size - 1)
        end = min(end, file_size - 1)

    if start < 0 or start >= file_size or end < start:
        raise HTTPException(
            status_code=status.HTTP_416_RANGE_NOT_SATISFIABLE,
            detail="Requested range not satisfiable",
            headers={"Content-Range": f"bytes */{file_size}"},
        )
    return start, end, True


# -------------------------------------------------------------
# 1. Creator Channels
# -------------------------------------------------------------

@router.post("/channels", response_model=ChannelResponse, status_code=status.HTTP_201_CREATED)
async def create_or_update_channel(
    payload: ChannelCreatePayload,
    current_user: dict = Depends(get_current_user)
):
    try:
        channel = await video_service.get_or_create_channel(
            current_user=current_user,
            handle=payload.handle,
            name=payload.name,
            description=payload.description,
            avatar_url=payload.avatar_url,
            banner_url=payload.banner_url
        )
        return ChannelResponse(
            id=str(channel["_id"]),
            owner_id=channel["owner_id"],
            handle=channel["handle"],
            name=channel["name"],
            description=channel.get("description"),
            avatar_url=channel.get("avatar_url"),
            banner_url=channel.get("banner_url"),
            subscriber_count=channel.get("subscriber_count", 0),
            video_count=channel.get("video_count", 0),
            shorts_count=channel.get("shorts_count", 0),
            is_subscribed=False,
            is_owner=True,
            created_at=channel["created_at"],
            updated_at=channel["updated_at"]
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/channels/{identifier}", response_model=ChannelResponse)
async def get_channel(identifier: str, current_user: Optional[dict] = Depends(get_optional_current_user)):
    try:
        current_uid = current_user["id"] if current_user else None
        channel = await video_service.get_channel_by_id_or_handle(identifier, current_uid)
        return ChannelResponse(
            id=str(channel["_id"]),
            owner_id=channel["owner_id"],
            handle=channel["handle"],
            name=channel["name"],
            description=channel.get("description"),
            avatar_url=channel.get("avatar_url"),
            banner_url=channel.get("banner_url"),
            subscriber_count=channel.get("subscriber_count", 0),
            video_count=channel.get("video_count", 0),
            shorts_count=channel.get("shorts_count", 0),
            is_subscribed=channel.get("is_subscribed", False),
            is_owner=channel.get("is_owner", False),
            created_at=channel["created_at"],
            updated_at=channel["updated_at"]
        )
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/channels/{channel_id}/subscribe", status_code=status.HTTP_200_OK)
async def subscribe_channel(channel_id: str, current_user: dict = Depends(get_current_user)):
    try:
        return await video_service.toggle_channel_subscription(current_user, channel_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/channels/{channel_id}/analytics", response_model=CreatorAnalyticsResponse)
async def get_analytics(channel_id: str, current_user: dict = Depends(get_current_user)):
    try:
        return await video_service.get_channel_analytics(current_user, channel_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# -------------------------------------------------------------
# 2. Video Upload & Publishing (Cloudflare R2 + Local Dev Adapter)
# -------------------------------------------------------------

@router.post("", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
async def upload_video(
    title: str = Form(..., min_length=2, max_length=150),
    description: Optional[str] = Form(None, max_length=2000),
    thumbnail_url: Optional[str] = Form(None, max_length=500),
    visibility: str = Form("public"),
    category: str = Form("General"),
    is_short: bool = Form(False),
    channel_id: Optional[str] = Form(None),
    audio_title: Optional[str] = Form(None),
    audio_artist: Optional[str] = Form(None),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    check_video_upload_rate_limit(current_user["id"])

    if visibility not in ("public", "unlisted", "private"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Visibility must be 'public', 'unlisted', or 'private'")

    content_type = (file.content_type or "").lower().split(";")[0].strip()
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported format '{content_type}'. Allowed: MP4, WebM, Ogg, QuickTime"
        )

    ext = ALLOWED_MIME_TYPES[content_type]
    random_filename = f"{uuid.uuid4().hex}{ext}"
    quarantine_path = os.path.join(QUARANTINE_DIR, f"quarantine_{random_filename}")

    total_bytes = 0
    header_checked = False

    try:
        async with aiofiles.open(quarantine_path, "wb") as out_file:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break

                if not header_checked:
                    if not verify_video_magic_bytes(chunk[:32]):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Uploaded file signature does not match a valid video stream format"
                        )
                    header_checked = True

                total_bytes += len(chunk)
                if total_bytes > MAX_VIDEO_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Video file exceeds maximum size limit of {MAX_VIDEO_SIZE // (1024 * 1024)}MB"
                    )
                await out_file.write(chunk)
    except Exception as e:
        if os.path.exists(quarantine_path):
            try:
                os.remove(quarantine_path)
            except Exception:
                pass
        if isinstance(e, HTTPException):
            raise e
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Failed to write video: {e}")

    # Security scan
    scan_passed = await scan_quarantined_media(quarantine_path, content_type)
    if not scan_passed:
        if os.path.exists(quarantine_path):
            try:
                os.remove(quarantine_path)
            except Exception:
                pass
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Uploaded video failed security quarantine scan")

    adapter = get_storage_adapter()
    is_public_obj = visibility == "public"
    if isinstance(adapter, S3StorageAdapter):
        storage_key = f"videos/{current_user['id'][:8]}/{random_filename}"
        storage_provider = "r2"
        try:
            await adapter.save_file(quarantine_path, storage_key, content_type, is_public=is_public_obj)
        finally:
            if os.path.exists(quarantine_path):
                try:
                    os.remove(quarantine_path)
                except Exception:
                    pass
    else:
        storage_key = random_filename
        storage_provider = "local"
        dest_path = os.path.join(STORAGE_DIR, random_filename)
        os.rename(quarantine_path, dest_path)

    now = datetime.now(timezone.utc)
    db = get_database()

    # Channel resolution
    channel_handle = None
    channel_name = None
    if channel_id and ObjectId.is_valid(channel_id):
        ch = await db.creator_channels.find_one({"_id": ObjectId(channel_id)})
        if ch:
            channel_handle = ch.get("handle")
            channel_name = ch.get("name")
            counter = "shorts_count" if is_short else "video_count"
            await db.creator_channels.update_one({"_id": ObjectId(channel_id)}, {"$inc": {counter: 1}})

    video_doc = {
        "owner_id": current_user["id"],
        "owner_username": current_user["username"],
        "owner_full_name": current_user["full_name"],
        "owner_avatar": current_user.get("avatar_url"),
        "channel_id": channel_id,
        "channel_handle": channel_handle,
        "channel_name": channel_name,
        "title": title.strip(),
        "description": description.strip() if description else None,
        "storage_key": storage_key,
        "storage_provider": storage_provider,
        "mime_type": content_type,
        "file_size_bytes": total_bytes,
        "duration_seconds": 60.0 if is_short else 120.0,
        "thumbnail_url": thumbnail_url,
        "visibility": visibility,
        "status": "published",
        "moderation_status": "approved",
        "is_deleted": False,
        "category": category,
        "is_short": is_short,
        "aspect_ratio": "9:16" if is_short else "16:9",
        "audio_title": audio_title,
        "audio_artist": audio_artist,
        "likes": [],
        "dislikes": [],
        "likes_count": 0,
        "dislikes_count": 0,
        "comments_count": 0,
        "view_count": 0,
        "created_at": now,
        "updated_at": now
    }

    insert_res = await db.videos.insert_one(video_doc)
    video_doc["_id"] = insert_res.inserted_id

    return build_video_response(video_doc, current_user["id"], set())


# -------------------------------------------------------------
# 3. Feeds, YouTube Proxy, Saved Videos, Playlists & History
# (All static/prefixed routes registered BEFORE /{video_id})
# -------------------------------------------------------------

@router.get("", response_model=List[VideoResponse])
async def list_videos(
    category: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    is_short: Optional[bool] = Query(None),
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    current_uid = current_user["id"] if current_user else None
    videos = await video_service.get_feed_videos(
        current_uid, category=category, limit=limit, offset=offset, is_short=is_short
    )
    saved_ids = await video_service.get_saved_video_ids(current_uid)
    return [build_video_response(v, current_uid, saved_ids) for v in videos]


@router.get("/shorts", response_model=List[VideoResponse])
async def list_shorts_feed(
    limit: int = Query(15, ge=1, le=30),
    offset: int = Query(0, ge=0),
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    current_uid = current_user["id"] if current_user else None
    shorts = await video_service.get_feed_videos(
        current_uid, limit=limit, offset=offset, is_short=True
    )
    saved_ids = await video_service.get_saved_video_ids(current_uid)
    return [build_video_response(s, current_uid, saved_ids) for s in shorts]


@router.get("/recommendations", response_model=List[VideoResponse])
async def get_recommendations(
    category: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    current_uid = current_user["id"] if current_user else None
    videos = await video_service.get_recommended_videos(
        current_uid, category=category, limit=limit, offset=offset
    )
    saved_ids = await video_service.get_saved_video_ids(current_uid)
    return [build_video_response(v, current_uid, saved_ids) for v in videos]


@router.get("/youtube", response_model=YouTubeSearchResponse)
async def get_youtube_videos_proxy(
    q: Optional[str] = Query(None, description="Search keyword"),
    category: Optional[str] = Query(None, description="Category filter"),
    max_results: int = Query(15, ge=1, le=50),
    page_token: Optional[str] = Query(None, description="YouTube API pagination token"),
    pageToken: Optional[str] = Query(None, description="YouTube API pagination token alias"),
):
    """
    Sovereign YouTube Data API v3 Proxy:
    Supports cursor pagination (`page_token` / `pageToken`), single-batch `videos.list` enrichment
    for duration & viewCount, embeddability filtering, and Redis/memory TTL quota caching.
    """
    effective_token = page_token or pageToken
    return await youtube_service.search_youtube_videos(
        q=q,
        category=category,
        max_results=max_results,
        page_token=effective_token,
    )


@router.get("/youtube/shorts/catalog", response_model=YouTubeShortsResponse)
async def get_youtube_shorts_catalog(
    category: Optional[str] = Query(None, description="Category filter"),
    language: Optional[str] = Query(None, description="Preferred language code (e.g. ta, hi, ml, te, kn, mr, bn, pa, gu, en)"),
    max_results: int = Query(15, ge=1, le=50, description="Maximum number of candidates"),
    page_token: Optional[str] = Query(None, description="Pagination cursor token"),
):
    """
    Returns authentic, embeddable YouTube short-form candidates catalog.
    Adheres strictly to zero-fake policies: all video IDs are authentic, public, and embeddable.
    """
    return youtube_service.get_verified_shorts_catalog(
        language=language,
        category=category,
        max_results=max_results,
        page_token=page_token,
    )


@router.get("/youtube/shorts", response_model=YouTubeShortsResponse)
async def get_youtube_shorts_proxy(
    q: Optional[str] = Query(None, description="Search keyword for shorts"),
    category: Optional[str] = Query(None, description="Category filter (e.g. Comedy, Tech, Music)"),
    region_code: str = Query("IN", min_length=2, max_length=2, description="2-letter ISO region/country code"),
    language: Optional[str] = Query(None, description="Preferred language code (e.g. ta, hi, ml, te, kn, mr, bn, pa, gu, en)"),
    max_results: int = Query(15, ge=1, le=50, description="Maximum number of candidate shorts to return"),
    page_token: Optional[str] = Query(None, description="YouTube pagination cursor token"),
    pageToken: Optional[str] = Query(None, description="YouTube pagination cursor token alias"),
):
    """
    Sovereign YouTube Shorts Discovery & Continuous Stream Proxy:
    - Queries official YouTube Data API v3 with `videoDuration='short'` and `videoEmbeddable='true'`.
    - Automatically enriches queries with regional language & #shorts hashtags.
    - Single-batch metadata lookup filters videos > 90s, non-embeddable, or non-public.
    - Prioritizes true vertical short candidates (duration <= 60s).
    - Multi-tier TTL quota protection with Redis and bounded local fallback cache.
    """
    effective_token = page_token or pageToken
    return await youtube_service.search_youtube_shorts(
        q=q,
        category=category,
        region_code=region_code,
        language=language,
        max_results=max_results,
        page_token=effective_token,
    )


@router.get("/youtube/categories", response_model=YouTubeCategoriesResponse)
async def get_youtube_categories_proxy(
    region_code: str = Query("IN", min_length=2, max_length=2, description="2-letter ISO region code")
):
    """Official YouTube videoCategories.list discovery endpoint with 24h TTL caching."""
    return await youtube_service.get_youtube_categories(region_code=region_code)


@router.get("/youtube/status/{video_id}", response_model=YouTubeVideoStatusResponse)
async def get_youtube_video_status(video_id: str):
    """Checks YouTube video existence, embeddability, duration, and viewCount."""
    return await youtube_service.get_youtube_video_status(video_id)


# -------------------------------------------------------------
# 4. Saved Videos (GET / POST / DELETE /videos/saved)
# -------------------------------------------------------------

@router.get("/saved", response_model=List[SavedVideoEntryResponse])
async def list_saved_videos_endpoint(
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    rows = await video_service.list_saved_videos(current_user, limit=limit, offset=offset)
    saved_ids = await video_service.get_saved_video_ids(current_user["id"])
    responses: List[SavedVideoEntryResponse] = []
    for row in rows:
        entry = row["entry"]
        vid_doc = row["video"]
        yt_meta = entry.get("youtube_metadata")
        responses.append(
            SavedVideoEntryResponse(
                id=str(entry["_id"]),
                user_id=entry["user_id"],
                source=entry["source"],
                video_id=entry["video_id"],
                saved_at=entry["saved_at"],
                video=build_video_response(vid_doc, current_user["id"], saved_ids) if vid_doc else None,
                youtube_metadata=YouTubeSavedMetadata(**yt_meta) if yt_meta else None,
            )
        )
    return responses


@router.post("/saved", response_model=SavedVideoEntryResponse, status_code=status.HTTP_201_CREATED)
async def save_video_endpoint(
    payload: SaveVideoPayload,
    current_user: dict = Depends(get_current_user),
):
    try:
        res = await video_service.save_video_for_user(current_user, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    entry = res["entry"]
    vid_doc = res["video"]
    yt_meta = entry.get("youtube_metadata")
    saved_ids = {entry["video_id"]} if entry["source"] == "zenova" else set()
    return SavedVideoEntryResponse(
        id=str(entry["_id"]),
        user_id=entry["user_id"],
        source=entry["source"],
        video_id=entry["video_id"],
        saved_at=entry["saved_at"],
        video=build_video_response(vid_doc, current_user["id"], saved_ids) if vid_doc else None,
        youtube_metadata=YouTubeSavedMetadata(**yt_meta) if yt_meta else None,
    )


@router.delete("/saved/{video_id}", status_code=status.HTTP_200_OK)
async def unsave_video_by_path(
    video_id: str,
    source: Optional[str] = Query(None, pattern="^(zenova|youtube)$"),
    current_user: dict = Depends(get_current_user),
):
    try:
        return await video_service.unsave_video_for_user(current_user, video_id, source=source)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/saved", status_code=status.HTTP_200_OK)
async def unsave_video_by_query(
    video_id: str = Query(..., min_length=1, max_length=64),
    source: Optional[str] = Query(None, pattern="^(zenova|youtube)$"),
    current_user: dict = Depends(get_current_user),
):
    try:
        return await video_service.unsave_video_for_user(current_user, video_id, source=source)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


# -------------------------------------------------------------
# 5. Playlists (Static & Prefixed Routes Placed Before /{video_id})
# -------------------------------------------------------------

@router.get("/playlists", response_model=List[PlaylistResponse])
async def list_playlists(
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    docs = await video_service.list_user_playlists(current_user, limit=limit, offset=offset)
    return [_playlist_to_response(p) for p in docs]


@router.post("/playlists", response_model=PlaylistResponse, status_code=status.HTTP_201_CREATED)
async def create_new_playlist(payload: PlaylistCreatePayload, current_user: dict = Depends(get_current_user)):
    p = await video_service.create_playlist(
        current_user=current_user,
        title=payload.title,
        description=payload.description,
        visibility=payload.visibility,
        video_ids=payload.video_ids
    )
    return _playlist_to_response(p)


@router.get("/playlists/{playlist_id}", response_model=PlaylistDetailResponse)
async def get_playlist_detail_endpoint(
    playlist_id: str,
    current_user: Optional[dict] = Depends(get_optional_current_user),
):
    try:
        res = await video_service.get_playlist_detail(playlist_id, current_user)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    current_uid = current_user["id"] if current_user else None
    saved_ids = await video_service.get_saved_video_ids(current_uid)
    base = _playlist_to_response(res["playlist"]).model_dump()
    return PlaylistDetailResponse(
        **base,
        videos=[build_video_response(v, current_uid, saved_ids) for v in res["videos"]],
    )


@router.delete("/playlists/{playlist_id}", status_code=status.HTTP_200_OK)
async def delete_playlist_endpoint(playlist_id: str, current_user: dict = Depends(get_current_user)):
    try:
        return await video_service.delete_playlist(current_user, playlist_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.post("/playlists/{playlist_id}/videos/{video_id}", status_code=status.HTTP_200_OK)
async def add_to_playlist(
    playlist_id: str,
    video_id: str,
    action: str = Query("add", pattern="^(add|remove)$"),
    current_user: dict = Depends(get_current_user)
):
    try:
        return await video_service.add_or_remove_playlist_video(current_user, playlist_id, video_id, action)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


# -------------------------------------------------------------
# 6. Watch History
# -------------------------------------------------------------

@router.get("/user/history", response_model=List[WatchHistoryResponse])
async def get_history(
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    entries = await video_service.get_user_watch_history(current_user, limit=limit, offset=offset)
    saved_ids = await video_service.get_saved_video_ids(current_user["id"])
    return [
        WatchHistoryResponse(
            video=build_video_response(e["video"], current_user["id"], saved_ids),
            playback_position_seconds=e["playback_position_seconds"],
            last_watched_at=e["last_watched_at"],
            completed=e["completed"]
        )
        for e in entries
    ]


@router.delete("/user/history/{video_id}", status_code=status.HTTP_200_OK)
async def delete_history_item(video_id: str, current_user: dict = Depends(get_current_user)):
    try:
        return await video_service.delete_watch_history_entry(current_user, video_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.delete("/user/history", status_code=status.HTTP_200_OK)
async def clear_history_endpoint(current_user: dict = Depends(get_current_user)):
    return await video_service.clear_watch_history(current_user)


@router.get("/users/{user_id}", response_model=List[VideoResponse])
async def list_user_videos(
    user_id: str,
    limit: int = Query(25, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    db = get_database()
    if db is None:
        return []

    my_id = current_user["id"] if current_user else None
    query: dict = {
        "owner_id": user_id,
        "is_deleted": {"$ne": True},
        "moderation_status": {"$nin": ["removed", "rejected", "hidden"]},
    }
    if my_id != user_id:
        query["visibility"] = "public"
        query["status"] = "published"

    cursor = db.videos.find(query).sort("created_at", -1).skip(offset).limit(limit)
    saved_ids = await video_service.get_saved_video_ids(my_id)
    items = []
    async for v in cursor:
        items.append(build_video_response(v, my_id, saved_ids))
    return items


# -------------------------------------------------------------
# 7. Dynamic Video Detail, R2/Local Range Streaming & Engagement
# -------------------------------------------------------------

@router.get("/{video_id}", response_model=VideoResponse)
async def get_video_detail(
    video_id: str,
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    db = get_database()
    try:
        video_obj = ObjectId(video_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid video ID")

    video = await db.videos.find_one({"_id": video_obj})
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    current_uid = current_user["id"] if current_user else None
    _check_video_stream_access(video, current_uid)
    saved_ids = await video_service.get_saved_video_ids(current_uid)
    return build_video_response(video, current_uid, saved_ids)


@router.get("/{video_id}/stream-url", response_model=VideoStreamUrlResponse)
async def get_video_stream_url(
    video_id: str,
    expires_in: int = Query(300, ge=30, le=900),
    current_user: Optional[dict] = Depends(get_optional_current_user),
):
    """Returns a short-lived signed Cloudflare R2 URL (or authorized backend stream route in dev)."""
    db = get_database()
    try:
        video_obj = ObjectId(video_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid video ID")

    video = await db.videos.find_one({"_id": video_obj})
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    current_uid = current_user["id"] if current_user else None
    _check_video_stream_access(video, current_uid)

    mime_type = (video.get("mime_type") or "").lower().split(";")[0].strip()
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Invalid video media type")

    adapter = get_storage_adapter()
    meta = await adapter.get_object_metadata(video["storage_key"])
    if meta is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video stream object missing")

    if isinstance(adapter, S3StorageAdapter):
        signed_url = await adapter.generate_presigned_download(video["storage_key"], expires_in=expires_in)
        return VideoStreamUrlResponse(
            video_id=video_id,
            stream_url=signed_url,
            delivery="presigned_r2",
            expires_in=expires_in,
            mime_type=mime_type,
        )

    return VideoStreamUrlResponse(
        video_id=video_id,
        stream_url=f"/api/v1/videos/{video_id}/stream",
        delivery="backend_stream",
        expires_in=expires_in,
        mime_type=mime_type,
    )


@router.get("/{video_id}/stream")
async def stream_video(
    video_id: str,
    request: Request,
    range: Optional[str] = Header(None),
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    db = get_database()
    try:
        video_obj = ObjectId(video_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid video ID")

    video = await db.videos.find_one({"_id": video_obj})
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    current_uid = current_user["id"] if current_user else None
    _check_video_stream_access(video, current_uid)

    mime_type = (video.get("mime_type") or "").lower().split(";")[0].strip()
    if mime_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail="Unsupported video content type")

    adapter = get_storage_adapter()
    meta = await adapter.get_object_metadata(video["storage_key"])
    if meta is None or not meta.get("file_size"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video stream object not found")

    file_size = int(meta["file_size"])
    start, end, is_partial = _parse_byte_range(range, file_size)
    content_length = (end - start) + 1

    headers = {
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
        "Content-Type": mime_type,
        "Cache-Control": "private, max-age=60" if video.get("visibility") == "private" else "public, max-age=300",
    }
    if is_partial:
        headers["Content-Range"] = f"bytes {start}-{end}/{file_size}"

    return StreamingResponse(
        adapter.stream_range(video["storage_key"], start, end, CHUNK_SIZE),
        status_code=206 if is_partial else 200,
        headers=headers,
    )


@router.post("/{video_id}/view", status_code=status.HTTP_200_OK)
async def record_video_view(
    video_id: str,
    request: Request,
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    db = get_database()
    try:
        video_obj = ObjectId(video_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid video ID")

    video = await db.videos.find_one({"_id": video_obj})
    if not video or video.get("is_deleted"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    client_ip = request.client.host if request.client else "unknown"
    viewer_identifier = current_user["id"] if current_user else f"ip_{client_ip}"
    now = datetime.now(timezone.utc)

    cooldown_threshold = now - timedelta(minutes=10)
    existing_view = await db.video_views.find_one({
        "video_id": video_id,
        "viewer_identifier": viewer_identifier,
        "viewed_at": {"$gt": cooldown_threshold}
    })

    if not existing_view:
        await db.video_views.insert_one({
            "video_id": video_id,
            "viewer_identifier": viewer_identifier,
            "viewed_at": now
        })
        await db.videos.update_one(
            {"_id": video_obj},
            {"$inc": {"view_count": 1}}
        )
        return {"recorded": True}

    return {"recorded": False, "reason": "cooldown"}


@router.post("/{video_id}/feedback", status_code=status.HTTP_200_OK)
async def submit_feedback(
    video_id: str,
    type: str = Query("like", pattern="^(like|dislike)$"),
    current_user: dict = Depends(get_current_user)
):
    try:
        return await video_service.toggle_video_feedback(current_user, video_id, type)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{video_id}/like", status_code=status.HTTP_200_OK)
async def legacy_like(video_id: str, current_user: dict = Depends(get_current_user)):
    db = get_database()
    try:
        video_obj = ObjectId(video_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid video ID")
    my_id = current_user["id"]
    await db.videos.update_one({"_id": video_obj}, {"$addToSet": {"likes": my_id}})
    v = await db.videos.find_one({"_id": video_obj})
    if not v:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    likes_count = len(v.get("likes", []))
    await db.videos.update_one({"_id": video_obj}, {"$set": {"likes_count": likes_count}})
    return {"success": True, "likes_count": likes_count, "is_liked": True}


@router.delete("/{video_id}/like", status_code=status.HTTP_200_OK)
async def legacy_unlike(video_id: str, current_user: dict = Depends(get_current_user)):
    db = get_database()
    try:
        video_obj = ObjectId(video_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid video ID")
    my_id = current_user["id"]
    await db.videos.update_one({"_id": video_obj}, {"$pull": {"likes": my_id}})
    v = await db.videos.find_one({"_id": video_obj})
    if not v:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    likes_count = len(v.get("likes", []))
    await db.videos.update_one({"_id": video_obj}, {"$set": {"likes_count": likes_count}})
    return {"success": True, "likes_count": likes_count, "is_liked": False}


@router.get("/{video_id}/comments", response_model=List[VideoCommentResponse])
async def list_comments(video_id: str, limit: int = Query(50, ge=1, le=100)):
    db = get_database()
    cursor = db.video_comments.find({"video_id": video_id}).sort("created_at", 1).limit(limit)
    comments = []
    async for c in cursor:
        comments.append(VideoCommentResponse(
            id=str(c["_id"]),
            video_id=c["video_id"],
            author_id=c["author_id"],
            author_username=c["author_username"],
            author_full_name=c["author_full_name"],
            author_avatar=c.get("author_avatar"),
            content=c["content"],
            parent_comment_id=c.get("parent_comment_id"),
            created_at=c["created_at"],
            is_pinned=c.get("is_pinned", False),
            is_owner=False
        ))
    return comments


@router.post("/{video_id}/comments", response_model=VideoCommentResponse, status_code=status.HTTP_201_CREATED)
async def add_comment(
    video_id: str,
    payload: VideoCommentCreate,
    current_user: dict = Depends(get_current_user)
):
    check_video_comment_rate_limit(current_user["id"])
    doc = await video_service.add_video_comment(
        current_user=current_user,
        video_id=video_id,
        content=payload.content,
        parent_comment_id=payload.parent_comment_id
    )
    return VideoCommentResponse(
        id=str(doc["_id"]),
        video_id=doc["video_id"],
        author_id=doc["author_id"],
        author_username=doc["author_username"],
        author_full_name=doc["author_full_name"],
        author_avatar=doc.get("author_avatar"),
        content=doc["content"],
        parent_comment_id=doc.get("parent_comment_id"),
        created_at=doc["created_at"],
        is_pinned=False,
        is_owner=True
    )


@router.post("/{video_id}/progress", status_code=status.HTTP_200_OK)
async def report_progress(
    video_id: str,
    payload: WatchProgressPayload,
    current_user: dict = Depends(get_current_user)
):
    try:
        return await video_service.record_watch_progress(
            current_user=current_user,
            video_id=video_id,
            position_seconds=payload.playback_position_seconds,
            duration_seconds=payload.duration_seconds,
            completed=payload.completed
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))


@router.get("/{video_id}/related", response_model=List[VideoResponse])
async def list_related_videos(
    video_id: str,
    limit: int = Query(6, ge=1, le=20),
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    db = get_database()
    if db is None:
        return []

    try:
        video_obj = ObjectId(video_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid video ID")

    video = await db.videos.find_one({"_id": video_obj})
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    my_id = current_user["id"] if current_user else None
    query: Dict[str, Any] = {
        "_id": {"$ne": video_obj},
        "visibility": "public",
        "status": "published",
        "is_deleted": {"$ne": True},
        "moderation_status": {"$nin": ["removed", "rejected", "hidden"]},
    }
    if my_id:
        blocked = await get_blocked_users(db, my_id)
        if blocked:
            query["owner_id"] = {"$nin": blocked}

    cursor = db.videos.find(query).sort("view_count", -1).limit(limit)
    saved_ids = await video_service.get_saved_video_ids(my_id)
    items = []
    async for v in cursor:
        items.append(build_video_response(v, my_id, saved_ids))
    return items


@router.patch("/{video_id}", response_model=VideoResponse)
async def update_video_metadata(
    video_id: str,
    update_in: VideoUpdate,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    try:
        video_obj = ObjectId(video_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid video ID")

    video = await db.videos.find_one({"_id": video_obj})
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    if video["owner_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot edit another user's video")

    update_fields: dict = {"updated_at": datetime.now(timezone.utc)}
    if update_in.title is not None:
        update_fields["title"] = update_in.title.strip()
    if update_in.description is not None:
        update_fields["description"] = update_in.description.strip()
    if update_in.thumbnail_url is not None:
        update_fields["thumbnail_url"] = update_in.thumbnail_url
    if update_in.visibility is not None:
        update_fields["visibility"] = update_in.visibility
    if update_in.category is not None:
        update_fields["category"] = update_in.category

    await db.videos.update_one({"_id": video_obj}, {"$set": update_fields})
    updated = await db.videos.find_one({"_id": video_obj})
    saved_ids = await video_service.get_saved_video_ids(current_user["id"])
    return build_video_response(updated, current_user["id"], saved_ids)


@router.delete("/{video_id}", status_code=status.HTTP_200_OK)
async def delete_video(video_id: str, current_user: dict = Depends(get_current_user)):
    db = get_database()
    try:
        video_obj = ObjectId(video_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid video ID")

    video = await db.videos.find_one({"_id": video_obj})
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    if video["owner_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete another user's video")

    storage_key = video.get("storage_key", "")
    adapter = get_storage_adapter()
    if video.get("storage_provider") in ("r2", "s3") and isinstance(adapter, S3StorageAdapter):
        try:
            await adapter.delete_file(storage_key)
        except Exception:
            pass
    else:
        file_path = os.path.join(STORAGE_DIR, storage_key)
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
            except Exception:
                pass

    await db.videos.delete_one({"_id": video_obj})
    await db.video_comments.delete_many({"video_id": video_id})
    await db.video_saves.delete_many({"source": "zenova", "video_id": video_id})
    await db.video_watch_history.delete_many({"video_id": video_id})
    return {"status": "deleted", "video_id": video_id}
