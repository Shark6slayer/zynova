"""
Zynova Video API Routes (Phase 27 Extended).
Exposes endpoints for:
- Creator channels (create, update, get by handle, subscriber counts).
- Video & Shorts upload, streaming, update, and deletion.
- Shorts continuous swipe-feed (`/videos/shorts`).
- Channel subscriptions (`/videos/channels/{id}/subscribe`).
- Video engagement (likes, dislikes, threaded comments, pinning).
- Watch progress and watch history (`/videos/history`).
- Playlists (`/videos/playlists`).
- Explainable recommendation feed (`/videos/recommendations`).
- Creator analytics (`/videos/channels/{id}/analytics`).
"""

import os
import uuid
import aiofiles
from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any
from fastapi import (
    APIRouter, HTTPException, status, Depends, Query, 
    UploadFile, File, Form, Request, Header
)
from fastapi.responses import StreamingResponse
from bson import ObjectId

from app.schemas.all_schemas import (
    ChannelCreatePayload,
    ChannelUpdatePayload,
    ChannelResponse,
    VideoResponse,
    VideoUpdate,
    VideoCommentCreate,
    VideoCommentResponse,
    PlaylistCreatePayload,
    PlaylistResponse,
    WatchProgressPayload,
    WatchHistoryResponse,
    CreatorAnalyticsResponse
)
from app.database.client import get_database
from app.api.deps import get_current_user, get_optional_current_user
from app.core.rate_limit import check_video_upload_rate_limit, check_video_comment_rate_limit
from app.core.scanner import scan_quarantined_media, QUARANTINE_DIR
from app.services import video_service
from app.services.identity_service import get_blocked_users

router = APIRouter(prefix="/videos", tags=["Zynova Video & Shorts Platform"])

# Local storage configuration
STORAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "storage", "videos"))
os.makedirs(STORAGE_DIR, exist_ok=True)

MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100MB max limit
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

def verify_video_magic_bytes(header_bytes: bytes) -> bool:
    if len(header_bytes) < 4:
        return False
    for magic in MAGIC_BYTES:
        if header_bytes.startswith(magic) or magic in header_bytes[:32]:
            return True
    return False

def build_video_response(v: dict, current_user_id: Optional[str] = None) -> VideoResponse:
    likes_list = v.get("likes", [])
    dislikes_list = v.get("dislikes", [])
    is_liked = (current_user_id in likes_list) if current_user_id else False
    is_owner = (current_user_id == v.get("owner_id")) if current_user_id else False

    return VideoResponse(
        id=str(v["_id"]),
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
        is_saved=False,
        is_owner=is_owner,
        created_at=v["created_at"],
        updated_at=v.get("updated_at", v["created_at"])
    )

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
# 2. Video Upload & Publishing
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
    dest_path = os.path.join(STORAGE_DIR, random_filename)

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

    os.rename(quarantine_path, dest_path)
    now = datetime.now(timezone.utc)
    db = get_database()

    # Channel resolution
    channel_handle = None
    channel_name = None
    if channel_id:
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
        "storage_key": random_filename,
        "mime_type": content_type,
        "file_size_bytes": total_bytes,
        "duration_seconds": 60.0 if is_short else 120.0,
        "thumbnail_url": thumbnail_url,
        "visibility": visibility,
        "status": "published",
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

    return build_video_response(video_doc, current_user["id"])

# -------------------------------------------------------------
# 3. Video Playback & Feeds
# -------------------------------------------------------------

@router.get("", response_model=List[VideoResponse])
async def list_videos(
    category: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50),
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    current_uid = current_user["id"] if current_user else None
    videos = await video_service.get_recommended_videos(current_uid, category=category, limit=limit)
    return [build_video_response(v, current_uid) for v in videos]

@router.get("/shorts", response_model=List[VideoResponse])
async def list_shorts_feed(
    limit: int = Query(15, ge=1, le=30),
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    db = get_database()
    current_uid = current_user["id"] if current_user else None
    query = {"is_short": True, "visibility": "public", "status": "published"}

    if current_uid:
        blocked = await get_blocked_users(db, current_uid)
        if blocked:
            query["owner_id"] = {"$nin": blocked}

    cursor = db.videos.find(query).sort("created_at", -1).limit(limit)
    shorts = []
    async for s in cursor:
        shorts.append(build_video_response(s, current_uid))
    return shorts

@router.get("/recommendations", response_model=List[VideoResponse])
async def get_recommendations(
    category: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=50),
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    current_uid = current_user["id"] if current_user else None
    videos = await video_service.get_recommended_videos(current_uid, category=category, limit=limit)
    return [build_video_response(v, current_uid) for v in videos]

@router.get("/youtube")
async def get_youtube_videos_proxy(
    q: Optional[str] = Query(None, description="Search keyword"),
    category: Optional[str] = Query(None, description="Category filter"),
    max_results: int = Query(15, ge=1, le=50)
):
    """
    Sovereign YouTube Proxy Endpoint:
    Queries real YouTube Data API v3 when YOUTUBE_API_KEY is configured on the backend.
    Never exposes API keys in mobile frontend.
    Returns clear unconfigured status without fabricated trending videos.
    """
    from app.core.config import settings
    import httpx

    api_key = settings.YOUTUBE_API_KEY
    if not api_key:
        return {
            "configured": False,
            "query": q or "",
            "category": category or "All",
            "videos": [],
            "message": "YouTube Data API key (YOUTUBE_API_KEY) not configured on the backend server. Real video search available via external handoff."
        }

    search_query = q or (f"{category} tech india" if category and category != "All" else "technology india")
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                "https://www.googleapis.com/youtube/v3/search",
                params={
                    "part": "snippet",
                    "q": search_query,
                    "type": "video",
                    "maxResults": max_results,
                    "key": api_key,
                }
            )
            if resp.status_code != 200:
                err_data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
                err_msg = err_data.get("error", {}).get("message", f"YouTube API error HTTP {resp.status_code}")
                return {
                    "configured": True,
                    "query": search_query,
                    "videos": [],
                    "message": err_msg
                }

            data = resp.json()
            items = []
            for item in data.get("items", []):
                snippet = item.get("snippet", {})
                vid_id = item.get("id", {}).get("videoId")
                if not vid_id:
                    continue
                thumbs = snippet.get("thumbnails", {})
                thumb_url = thumbs.get("high", {}).get("url") or thumbs.get("medium", {}).get("url") or ""
                items.append({
                    "id": vid_id,
                    "title": snippet.get("title", ""),
                    "description": snippet.get("description", ""),
                    "channelTitle": snippet.get("channelTitle", "YouTube Creator"),
                    "channelId": snippet.get("channelId"),
                    "publishedAt": snippet.get("publishedAt", ""),
                    "thumbnailUrl": thumb_url,
                    "category": category or "Tech"
                })

            return {
                "configured": True,
                "query": search_query,
                "videos": items
            }
    except Exception as e:
        return {
            "configured": True,
            "query": search_query,
            "videos": [],
            "message": f"Network error contacting YouTube Data API: {str(e)}"
        }

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

    # Privacy check: private videos accessible only to owner
    if video.get("visibility") == "private" and video.get("owner_id") != current_uid:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This video is private")

    return build_video_response(video, current_uid)

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

    # Authorize stream playback: private videos require owner authentication
    current_uid = current_user["id"] if current_user else None
    if video.get("visibility") == "private":
        if not current_uid or current_uid != video.get("owner_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Private video stream unauthorized: content is restricted to creator."
            )

    file_path = os.path.join(STORAGE_DIR, video["storage_key"])
    if not os.path.exists(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video stream file not found on disk")

    file_size = os.path.getsize(file_path)
    start = 0
    end = file_size - 1

    if range:
        try:
            bytes_range = range.replace("bytes=", "").split("-")
            start = int(bytes_range[0])
            if bytes_range[1]:
                end = int(bytes_range[1])
        except Exception:
            pass

    content_length = (end - start) + 1

    async def file_streamer():
        async with aiofiles.open(file_path, mode="rb") as f:
            await f.seek(start)
            bytes_to_read = content_length
            while bytes_to_read > 0:
                chunk_to_read = min(CHUNK_SIZE, bytes_to_read)
                data = await f.read(chunk_to_read)
                if not data:
                    break
                bytes_to_read -= len(data)
                yield data

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
        "Content-Type": video["mime_type"],
    }

    return StreamingResponse(file_streamer(), status_code=206, headers=headers)

# -------------------------------------------------------------
# 4. Engagement (Feedback, Comments, Progress, History, Views)
# -------------------------------------------------------------

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
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    client_ip = request.client.host if request.client else "unknown"
    viewer_identifier = current_user["id"] if current_user else f"ip_{client_ip}"
    now = datetime.now(timezone.utc)

    # 10-minute cooldown window per viewer
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
    video_obj = ObjectId(video_id)
    my_id = current_user["id"]
    await db.videos.update_one({"_id": video_obj}, {"$addToSet": {"likes": my_id}})
    v = await db.videos.find_one({"_id": video_obj})
    likes_count = len(v.get("likes", []))
    await db.videos.update_one({"_id": video_obj}, {"$set": {"likes_count": likes_count}})
    return {"success": True, "likes_count": likes_count, "is_liked": True}

@router.delete("/{video_id}/like", status_code=status.HTTP_200_OK)
async def legacy_unlike(video_id: str, current_user: dict = Depends(get_current_user)):
    db = get_database()
    video_obj = ObjectId(video_id)
    my_id = current_user["id"]
    await db.videos.update_one({"_id": video_obj}, {"$pull": {"likes": my_id}})
    v = await db.videos.find_one({"_id": video_obj})
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
    return await video_service.record_watch_progress(
        current_user=current_user,
        video_id=video_id,
        position_seconds=payload.playback_position_seconds,
        duration_seconds=payload.duration_seconds,
        completed=payload.completed
    )

@router.get("/user/history", response_model=List[WatchHistoryResponse])
async def get_history(current_user: dict = Depends(get_current_user)):
    entries = await video_service.get_user_watch_history(current_user)
    return [
        WatchHistoryResponse(
            video=build_video_response(e["video"], current_user["id"]),
            playback_position_seconds=e["playback_position_seconds"],
            last_watched_at=e["last_watched_at"],
            completed=e["completed"]
        )
        for e in entries
    ]

# -------------------------------------------------------------
# 5. Playlists
# -------------------------------------------------------------

@router.post("/playlists", response_model=PlaylistResponse, status_code=status.HTTP_201_CREATED)
async def create_new_playlist(payload: PlaylistCreatePayload, current_user: dict = Depends(get_current_user)):
    p = await video_service.create_playlist(
        current_user=current_user,
        title=payload.title,
        description=payload.description,
        visibility=payload.visibility,
        video_ids=payload.video_ids
    )
    return PlaylistResponse(
        id=str(p["_id"]),
        owner_id=p["owner_id"],
        owner_username=p["owner_username"],
        title=p["title"],
        description=p.get("description"),
        visibility=p["visibility"],
        video_ids=p["video_ids"],
        videos_count=p["videos_count"],
        created_at=p["created_at"],
        updated_at=p["updated_at"]
    )

@router.post("/playlists/{playlist_id}/videos/{video_id}", status_code=status.HTTP_200_OK)
async def add_to_playlist(
    playlist_id: str,
    video_id: str,
    action: str = Query("add", pattern="^(add|remove)$"),
    current_user: dict = Depends(get_current_user)
):
    try:
        return await video_service.add_or_remove_playlist_video(current_user, playlist_id, video_id, action)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

# -------------------------------------------------------------
# 7. User & Related Videos
# -------------------------------------------------------------

@router.get("/users/{user_id}", response_model=List[VideoResponse])
async def list_user_videos(
    user_id: str,
    limit: int = Query(25, ge=1, le=50),
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    db = get_database()
    if db is None:
        return []

    my_id = current_user["id"] if current_user else None
    query: dict = {"owner_id": user_id}
    if my_id != user_id:
        query["visibility"] = "public"

    cursor = db.videos.find(query).sort("created_at", -1).limit(limit)
    items = []
    async for v in cursor:
        items.append(build_video_response(v, my_id))
    return items

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
    query = {
        "_id": {"$ne": video_obj},
        "visibility": "public"
    }

    cursor = db.videos.find(query).sort("view_count", -1).limit(limit)
    items = []
    async for v in cursor:
        items.append(build_video_response(v, my_id))
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
    return build_video_response(updated, current_user["id"])

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

    file_path = os.path.join(STORAGE_DIR, video["storage_key"])
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass

    await db.videos.delete_one({"_id": video_obj})
    await db.video_comments.delete_many({"video_id": video_id})
    return {"status": "deleted", "video_id": video_id}

