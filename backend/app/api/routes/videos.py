import os
import uuid
import aiofiles
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import (
    APIRouter, HTTPException, status, Depends, Query, 
    UploadFile, File, Form, Request, Header
)
from fastapi.responses import StreamingResponse
from bson import ObjectId

from app.schemas.all_schemas import (
    VideoResponse,
    VideoUpdate,
    VideoCommentCreate,
    VideoCommentResponse
)
from app.database.client import get_database
from app.api.deps import get_current_user, get_optional_current_user
from app.core.rate_limit import check_video_upload_rate_limit, check_video_comment_rate_limit

router = APIRouter(prefix="/videos", tags=["Video Platform"])

# Local storage configuration
STORAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "storage", "videos"))
os.makedirs(STORAGE_DIR, exist_ok=True)

MAX_VIDEO_SIZE = 100 * 1024 * 1024  # 100MB max limit
CHUNK_SIZE = 1024 * 1024  # 1MB chunk size
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
    """Verifies that the initial bytes match known video magic signatures."""
    if len(header_bytes) < 4:
        return False
    for magic in MAGIC_BYTES:
        if header_bytes.startswith(magic) or magic in header_bytes[:32]:
            return True
    return False

# 1. Upload Video
@router.post("", response_model=VideoResponse, status_code=status.HTTP_201_CREATED)
async def upload_video(
    title: str = Form(..., min_length=2, max_length=150),
    description: Optional[str] = Form(None, max_length=2000),
    thumbnail_url: Optional[str] = Form(None, max_length=500),
    visibility: str = Form("public"),
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    check_video_upload_rate_limit(current_user["id"])

    if visibility not in ("public", "private"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Visibility must be 'public' or 'private'")

    content_type = (file.content_type or "").lower().split(";")[0].strip()
    if content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported format '{content_type}'. Allowed formats: MP4, WebM, Ogg, QuickTime"
        )

    ext = ALLOWED_MIME_TYPES[content_type]
    random_filename = f"{uuid.uuid4().hex}{ext}"
    dest_path = os.path.join(STORAGE_DIR, random_filename)

    total_bytes = 0
    header_checked = False

    try:
        async with aiofiles.open(dest_path, "wb") as out_file:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break

                if not header_checked:
                    # Check magic signature
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
                        detail=f"Video exceeds maximum allowed size of {MAX_VIDEO_SIZE // (1024 * 1024)}MB"
                    )

                await out_file.write(chunk)

    except HTTPException:
        # Cleanup incomplete file on failure
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except Exception:
                pass
        raise
    except Exception as e:
        if os.path.exists(dest_path):
            try:
                os.remove(dest_path)
            except Exception:
                pass
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Storage error: {str(e)}")

    db = get_database()
    now = datetime.now(timezone.utc)
    video_doc = {
        "owner_id": current_user["id"],
        "owner_username": current_user["username"],
        "owner_full_name": current_user["full_name"],
        "owner_avatar": current_user.get("avatar_url"),
        "title": title.strip(),
        "description": description.strip() if description else None,
        "storage_key": random_filename,
        "mime_type": content_type,
        "file_size_bytes": total_bytes,
        "duration_seconds": None,
        "thumbnail_url": thumbnail_url.strip() if thumbnail_url else None,
        "visibility": visibility,
        "status": "ready",
        "view_count": 0,
        "likes": [],
        "likes_count": 0,
        "comments_count": 0,
        "created_at": now,
        "updated_at": now
    }

    if db is not None:
        result = await db.videos.insert_one(video_doc)
        video_id = str(result.inserted_id)
    else:
        video_id = str(ObjectId())

    return VideoResponse(
        id=video_id,
        owner_id=video_doc["owner_id"],
        owner_username=video_doc["owner_username"],
        owner_full_name=video_doc["owner_full_name"],
        owner_avatar=video_doc["owner_avatar"],
        title=video_doc["title"],
        description=video_doc["description"],
        storage_key=video_doc["storage_key"],
        mime_type=video_doc["mime_type"],
        file_size_bytes=video_doc["file_size_bytes"],
        duration_seconds=video_doc["duration_seconds"],
        thumbnail_url=video_doc["thumbnail_url"],
        visibility=video_doc["visibility"],
        status=video_doc["status"],
        view_count=0,
        likes_count=0,
        comments_count=0,
        is_liked=False,
        is_owner=True,
        created_at=video_doc["created_at"],
        updated_at=video_doc["updated_at"]
    )

# 2. Get Video Feed
@router.get("", response_model=List[VideoResponse])
async def list_videos(
    limit: int = Query(20, ge=1, le=50),
    offset: int = Query(0, ge=0),
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    db = get_database()
    if db is None:
        return []

    my_id = current_user["id"] if current_user else None
    query = {"status": "ready", "visibility": "public"}

    cursor = db.videos.find(query).sort("created_at", -1).skip(offset).limit(limit)
    items = []
    async for v in cursor:
        likes_list = v.get("likes", [])
        items.append(VideoResponse(
            id=str(v["_id"]),
            owner_id=v["owner_id"],
            owner_username=v["owner_username"],
            owner_full_name=v["owner_full_name"],
            owner_avatar=v.get("owner_avatar"),
            title=v["title"],
            description=v.get("description"),
            storage_key=v["storage_key"],
            mime_type=v["mime_type"],
            file_size_bytes=v["file_size_bytes"],
            duration_seconds=v.get("duration_seconds"),
            thumbnail_url=v.get("thumbnail_url"),
            visibility=v.get("visibility", "public"),
            status=v.get("status", "ready"),
            view_count=v.get("view_count", 0),
            likes_count=len(likes_list),
            comments_count=v.get("comments_count", 0),
            is_liked=(my_id in likes_list) if my_id else False,
            is_owner=(my_id == v["owner_id"]) if my_id else False,
            created_at=v["created_at"],
            updated_at=v.get("updated_at", v["created_at"])
        ))
    return items

# 3. Get Video Detail
@router.get("/{video_id}", response_model=VideoResponse)
async def get_video_detail(
    video_id: str,
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    try:
        video_obj = ObjectId(video_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid video ID")

    video = await db.videos.find_one({"_id": video_obj})
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    my_id = current_user["id"] if current_user else None
    if video.get("visibility") == "private" and video["owner_id"] != my_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This video is private")

    likes_list = video.get("likes", [])
    return VideoResponse(
        id=str(video["_id"]),
        owner_id=video["owner_id"],
        owner_username=video["owner_username"],
        owner_full_name=video["owner_full_name"],
        owner_avatar=video.get("owner_avatar"),
        title=video["title"],
        description=video.get("description"),
        storage_key=video["storage_key"],
        mime_type=video["mime_type"],
        file_size_bytes=video["file_size_bytes"],
        duration_seconds=video.get("duration_seconds"),
        thumbnail_url=video.get("thumbnail_url"),
        visibility=video.get("visibility", "public"),
        status=video.get("status", "ready"),
        view_count=video.get("view_count", 0),
        likes_count=len(likes_list),
        comments_count=video.get("comments_count", 0),
        is_liked=(my_id in likes_list) if my_id else False,
        is_owner=(my_id == video["owner_id"]) if my_id else False,
        created_at=video["created_at"],
        updated_at=video.get("updated_at", video["created_at"])
    )

# 4. Stream Video Playback (HTTP Range Support)
@router.get("/{video_id}/stream")
async def stream_video(
    video_id: str,
    request: Request,
    range: Optional[str] = Header(None)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    try:
        video_obj = ObjectId(video_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid video ID")

    video = await db.videos.find_one({"_id": video_obj})
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    file_path = os.path.join(STORAGE_DIR, video["storage_key"])
    if not os.path.exists(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media file missing on storage")

    file_size = os.path.getsize(file_path)
    mime_type = video.get("mime_type", "video/mp4")

    # If no Range header, stream from beginning
    if not range:
        async def file_generator():
            async with aiofiles.open(file_path, mode="rb") as f:
                while chunk := await f.read(CHUNK_SIZE):
                    yield chunk

        headers = {
            "Content-Length": str(file_size),
            "Content-Type": mime_type,
            "Accept-Ranges": "bytes",
        }
        return StreamingResponse(file_generator(), headers=headers, media_type=mime_type)

    # Parse Range: bytes=start-end
    try:
        byte_range = range.replace("bytes=", "").split("-")
        start = int(byte_range[0]) if byte_range[0] else 0
        end = int(byte_range[1]) if len(byte_range) > 1 and byte_range[1] else file_size - 1
        end = min(end, file_size - 1)
        content_length = end - start + 1
    except Exception:
        raise HTTPException(status_code=status.HTTP_416_REQUESTED_RANGE_NOT_SATISFIABLE, detail="Invalid Range header")

    async def range_generator(start_byte: int, end_byte: int):
        async with aiofiles.open(file_path, mode="rb") as f:
            await f.seek(start_byte)
            bytes_left = end_byte - start_byte + 1
            while bytes_left > 0:
                read_amount = min(CHUNK_SIZE, bytes_left)
                chunk = await f.read(read_amount)
                if not chunk:
                    break
                bytes_left -= len(chunk)
                yield chunk

    headers = {
        "Content-Range": f"bytes {start}-{end}/{file_size}",
        "Accept-Ranges": "bytes",
        "Content-Length": str(content_length),
        "Content-Type": mime_type,
    }
    return StreamingResponse(
        range_generator(start, end),
        status_code=status.HTTP_206_PARTIAL_CONTENT,
        headers=headers,
        media_type=mime_type
    )

# 5. Record Video View (With IP/User deduplication window)
@router.post("/{video_id}/view", status_code=status.HTTP_200_OK)
async def record_video_view(
    video_id: str,
    request: Request,
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    db = get_database()
    if db is None:
        return {"recorded": False}

    try:
        video_obj = ObjectId(video_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid video ID")

    viewer_key = current_user["id"] if current_user else (request.client.host if request.client else "unknown")
    now = datetime.now(timezone.utc)

    # Check for view within the last 5 minutes to prevent spam inflation
    five_min_ago = datetime.fromtimestamp(now.timestamp() - 300, tz=timezone.utc)
    recent_view = await db.video_views.find_one({
        "video_id": video_id,
        "viewer_key": viewer_key,
        "created_at": {"$gte": five_min_ago}
    })

    if not recent_view:
        await db.video_views.insert_one({
            "video_id": video_id,
            "viewer_key": viewer_key,
            "created_at": now
        })
        await db.videos.update_one(
            {"_id": video_obj},
            {"$inc": {"view_count": 1}}
        )
        return {"recorded": True}

    return {"recorded": False, "reason": "cooldown"}

# 6. Like / Unlike Video
@router.post("/{video_id}/like", status_code=status.HTTP_200_OK)
async def like_video(video_id: str, current_user: dict = Depends(get_current_user)):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    try:
        video_obj = ObjectId(video_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid video ID")

    my_id = current_user["id"]
    await db.videos.update_one({"_id": video_obj}, {"$addToSet": {"likes": my_id}})
    v = await db.videos.find_one({"_id": video_obj})
    likes_count = len(v.get("likes", []))
    await db.videos.update_one({"_id": video_obj}, {"$set": {"likes_count": likes_count}})

    return {"success": True, "likes_count": likes_count, "is_liked": True}

@router.delete("/{video_id}/like", status_code=status.HTTP_200_OK)
async def unlike_video(video_id: str, current_user: dict = Depends(get_current_user)):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    try:
        video_obj = ObjectId(video_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid video ID")

    my_id = current_user["id"]
    await db.videos.update_one({"_id": video_obj}, {"$pull": {"likes": my_id}})
    v = await db.videos.find_one({"_id": video_obj})
    likes_count = len(v.get("likes", []))
    await db.videos.update_one({"_id": video_obj}, {"$set": {"likes_count": likes_count}})

    return {"success": True, "likes_count": likes_count, "is_liked": False}

# 7. Video Comments
@router.get("/{video_id}/comments", response_model=List[VideoCommentResponse])
async def list_video_comments(
    video_id: str,
    limit: int = Query(50, ge=1, le=100),
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    db = get_database()
    if db is None:
        return []

    my_id = current_user["id"] if current_user else None
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
            created_at=c["created_at"],
            is_owner=(my_id == c["author_id"]) if my_id else False
        ))
    return comments

@router.post("/{video_id}/comments", response_model=VideoCommentResponse, status_code=status.HTTP_201_CREATED)
async def add_video_comment(
    video_id: str,
    comment_in: VideoCommentCreate,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    try:
        video_obj = ObjectId(video_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid video ID")

    video = await db.videos.find_one({"_id": video_obj})
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    check_video_comment_rate_limit(current_user["id"])

    now = datetime.now(timezone.utc)
    comment_doc = {
        "video_id": video_id,
        "author_id": current_user["id"],
        "author_username": current_user["username"],
        "author_full_name": current_user["full_name"],
        "author_avatar": current_user.get("avatar_url"),
        "content": comment_in.content.strip(),
        "created_at": now
    }

    res = await db.video_comments.insert_one(comment_doc)
    await db.videos.update_one({"_id": video_obj}, {"$inc": {"comments_count": 1}})

    return VideoCommentResponse(
        id=str(res.inserted_id),
        video_id=video_id,
        author_id=current_user["id"],
        author_username=current_user["username"],
        author_full_name=current_user["full_name"],
        author_avatar=current_user.get("avatar_url"),
        content=comment_doc["content"],
        created_at=now,
        is_owner=True
    )

# 8. Delete Video
@router.delete("/{video_id}", status_code=status.HTTP_200_OK)
async def delete_video(video_id: str, current_user: dict = Depends(get_current_user)):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    try:
        video_obj = ObjectId(video_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid video ID")

    video = await db.videos.find_one({"_id": video_obj})
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    if video["owner_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete another creator's video")

    # Delete video file from storage
    file_path = os.path.join(STORAGE_DIR, video["storage_key"])
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
        except Exception:
            pass

    # Delete database records
    await db.videos.delete_one({"_id": video_obj})
    await db.video_comments.delete_many({"video_id": video_id})
    await db.video_views.delete_many({"video_id": video_id})

    return {"status": "deleted", "video_id": video_id}

# 9. Edit Video Metadata
@router.patch("/{video_id}", response_model=VideoResponse)
async def update_video_metadata(
    video_id: str,
    update_in: VideoUpdate,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    try:
        video_obj = ObjectId(video_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid video ID")

    video = await db.videos.find_one({"_id": video_obj})
    if not video:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    if video["owner_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot edit another creator's video")

    update_fields: dict = {"updated_at": datetime.now(timezone.utc)}
    if update_in.title is not None:
        update_fields["title"] = update_in.title.strip()
    if update_in.description is not None:
        update_fields["description"] = update_in.description.strip() if update_in.description else None
    if update_in.thumbnail_url is not None:
        update_fields["thumbnail_url"] = update_in.thumbnail_url.strip() if update_in.thumbnail_url else None
    if update_in.visibility is not None:
        update_fields["visibility"] = update_in.visibility

    await db.videos.update_one({"_id": video_obj}, {"$set": update_fields})
    updated_video = await db.videos.find_one({"_id": video_obj})

    likes_list = updated_video.get("likes", [])
    return VideoResponse(
        id=str(updated_video["_id"]),
        owner_id=updated_video["owner_id"],
        owner_username=updated_video["owner_username"],
        owner_full_name=updated_video["owner_full_name"],
        owner_avatar=updated_video.get("owner_avatar"),
        title=updated_video["title"],
        description=updated_video.get("description"),
        storage_key=updated_video["storage_key"],
        mime_type=updated_video["mime_type"],
        file_size_bytes=updated_video["file_size_bytes"],
        duration_seconds=updated_video.get("duration_seconds"),
        thumbnail_url=updated_video.get("thumbnail_url"),
        visibility=updated_video.get("visibility", "public"),
        status=updated_video.get("status", "ready"),
        view_count=updated_video.get("view_count", 0),
        likes_count=len(likes_list),
        comments_count=updated_video.get("comments_count", 0),
        is_liked=(current_user["id"] in likes_list),
        is_owner=True,
        created_at=updated_video["created_at"],
        updated_at=updated_video.get("updated_at", updated_video["created_at"])
    )

# 10. List Creator / User Videos
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
    query: dict = {"owner_id": user_id, "status": "ready"}
    # Only the creator themselves can see private videos
    if my_id != user_id:
        query["visibility"] = "public"

    cursor = db.videos.find(query).sort("created_at", -1).limit(limit)
    items = []
    async for v in cursor:
        likes_list = v.get("likes", [])
        items.append(VideoResponse(
            id=str(v["_id"]),
            owner_id=v["owner_id"],
            owner_username=v["owner_username"],
            owner_full_name=v["owner_full_name"],
            owner_avatar=v.get("owner_avatar"),
            title=v["title"],
            description=v.get("description"),
            storage_key=v["storage_key"],
            mime_type=v["mime_type"],
            file_size_bytes=v["file_size_bytes"],
            duration_seconds=v.get("duration_seconds"),
            thumbnail_url=v.get("thumbnail_url"),
            visibility=v.get("visibility", "public"),
            status=v.get("status", "ready"),
            view_count=v.get("view_count", 0),
            likes_count=len(likes_list),
            comments_count=v.get("comments_count", 0),
            is_liked=(my_id in likes_list) if my_id else False,
            is_owner=(my_id == v["owner_id"]) if my_id else False,
            created_at=v["created_at"],
            updated_at=v.get("updated_at", v["created_at"])
        ))
    return items

# 11. Related Videos (Discovery based on other videos from same or other public creators)
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
        "status": "ready",
        "visibility": "public"
    }

    cursor = db.videos.find(query).sort("view_count", -1).limit(limit)
    items = []
    async for v in cursor:
        likes_list = v.get("likes", [])
        items.append(VideoResponse(
            id=str(v["_id"]),
            owner_id=v["owner_id"],
            owner_username=v["owner_username"],
            owner_full_name=v["owner_full_name"],
            owner_avatar=v.get("owner_avatar"),
            title=v["title"],
            description=v.get("description"),
            storage_key=v["storage_key"],
            mime_type=v["mime_type"],
            file_size_bytes=v["file_size_bytes"],
            duration_seconds=v.get("duration_seconds"),
            thumbnail_url=v.get("thumbnail_url"),
            visibility=v.get("visibility", "public"),
            status=v.get("status", "ready"),
            view_count=v.get("view_count", 0),
            likes_count=len(likes_list),
            comments_count=v.get("comments_count", 0),
            is_liked=(my_id in likes_list) if my_id else False,
            is_owner=(my_id == v["owner_id"]) if my_id else False,
            created_at=v["created_at"],
            updated_at=v.get("updated_at", v["created_at"])
        ))
    return items
