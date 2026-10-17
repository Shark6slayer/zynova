import os
import uuid
import aiofiles
from fastapi import APIRouter, HTTPException, status, Depends, Query, UploadFile, File
from fastapi.responses import StreamingResponse
from datetime import datetime, timezone
from typing import List, Optional
from bson import ObjectId
import html

from app.schemas.all_schemas import (
    SocialProfileResponse,
    PostCreate,
    PostUpdate,
    PostResponse,
    CommentCreate,
    CommentResponse,
    ReportCreate,
    ReportResponse,
    UserPublicSummary
)
from app.api.deps import get_current_user, get_optional_current_user
from app.database.client import get_database
from app.core.rate_limit import (
    check_social_post_rate_limit,
    check_comment_rate_limit,
    check_report_rate_limit
)
from app.core.scanner import scan_quarantined_media, QUARANTINE_DIR

# Media storage configuration
MEDIA_STORAGE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "..", "storage", "media"))
os.makedirs(MEDIA_STORAGE_DIR, exist_ok=True)

MAX_MEDIA_SIZE = 50 * 1024 * 1024  # 50MB max limit
CHUNK_SIZE = 1024 * 1024

ALLOWED_IMAGE_MIMES = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/gif": ".gif"
}

ALLOWED_VIDEO_MIMES = {
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "video/ogg": ".ogv",
    "video/quicktime": ".mov"
}

IMAGE_MAGIC_BYTES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"RIFF": "image/webp",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif"
}

VIDEO_MAGIC_BYTES = {
    b"\x00\x00\x00\x18ftyp": "video/mp4",
    b"\x00\x00\x00\x20ftyp": "video/mp4",
    b"\x00\x00\x00\x1cftyp": "video/mp4",
    b"\x1a\x45\xdf\xa3": "video/webm",
    b"OggS": "video/ogg",
    b"\x00\x00\x00\x14ftypqt": "video/quicktime"
}

def verify_media_magic(header: bytes, is_video: bool) -> bool:
    if len(header) < 4:
        return False
    if is_video:
        for magic in VIDEO_MAGIC_BYTES:
            if header.startswith(magic) or magic in header[:32]:
                return True
    else:
        for magic in IMAGE_MAGIC_BYTES:
            if header.startswith(magic):
                return True
    return False

router = APIRouter(prefix="/social", tags=["Social Network"])

def sanitize_text(text: str) -> str:
    return html.escape(text.strip())

# 1. Social User Profile View
@router.get("/profiles/{user_id}", response_model=SocialProfileResponse)
async def get_social_profile(
    user_id: str,
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    try:
        user_obj = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID")

    target_user = await db.users.find_one({"_id": user_obj})
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    followers_count = await db.follows.count_documents({"following_id": user_id})
    following_count = await db.follows.count_documents({"follower_id": user_id})
    posts_count = await db.posts.count_documents({"author_id": user_id})

    # Check if current user is following target user
    is_following = False
    my_id = current_user["id"] if current_user else None
    if my_id and my_id != user_id:
        existing_follow = await db.follows.find_one({
            "follower_id": my_id,
            "following_id": user_id
        })
        is_following = existing_follow is not None

    return SocialProfileResponse(
        id=user_id,
        username=target_user["username"],
        full_name=target_user["full_name"],
        avatar_url=target_user.get("avatar_url"),
        bio=target_user.get("bio"),
        created_at=target_user.get("created_at", datetime.now(timezone.utc)),
        followers_count=followers_count,
        following_count=following_count,
        posts_count=posts_count,
        is_following=is_following,
        is_self=(my_id == user_id) if my_id else False
    )

# 2. Follow User
@router.post("/profiles/{user_id}/follow", status_code=status.HTTP_200_OK)
async def follow_user(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    my_id = current_user["id"]
    if my_id == user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot follow yourself")

    try:
        target_obj = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID")

    target = await db.users.find_one({"_id": target_obj})
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found")

    # Upsert to prevent duplicate-follow race conditions
    now = datetime.now(timezone.utc)
    res = await db.follows.update_one(
        {"follower_id": my_id, "following_id": user_id},
        {"$setOnInsert": {"follower_id": my_id, "following_id": user_id, "created_at": now}},
        upsert=True
    )

    # Trigger notification if this is a newly created follow
    if res.upserted_id:
        from app.services.notification_service import create_event_notification
        await create_event_notification(
            recipient_user_id=user_id,
            actor_user_id=my_id,
            category="social",
            event_type="social_follow",
            title=f"{current_user['full_name']} started following you",
            desc=f"@{current_user['username']} is now following your updates.",
            navigation_target=f"social:user:{my_id}",
            metadata={"follower_id": my_id, "follower_username": current_user["username"]},
            event_id=f"follow_{my_id}_{user_id}"
        )

    return {"status": "following", "following_id": user_id}

# 3. Unfollow User
@router.delete("/profiles/{user_id}/follow", status_code=status.HTTP_200_OK)
async def unfollow_user(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    my_id = current_user["id"]
    await db.follows.delete_one({"follower_id": my_id, "following_id": user_id})
    return {"status": "unfollowed", "following_id": user_id}

# 4. List Followers
@router.get("/profiles/{user_id}/followers", response_model=List[UserPublicSummary])
async def list_followers(
    user_id: str,
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        return []

    cursor = db.follows.find({"following_id": user_id}).limit(limit)
    follower_ids = [ObjectId(f["follower_id"]) for f in await cursor.to_list(length=limit)]

    if not follower_ids:
        return []

    users_cursor = db.users.find({"_id": {"$in": follower_ids}})
    results = []
    async for u in users_cursor:
        results.append(UserPublicSummary(
            id=str(u["_id"]),
            username=u["username"],
            full_name=u["full_name"],
            avatar_url=u.get("avatar_url")
        ))
    return results

# 5. List Following
@router.get("/profiles/{user_id}/following", response_model=List[UserPublicSummary])
async def list_following(
    user_id: str,
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        return []

    cursor = db.follows.find({"follower_id": user_id}).limit(limit)
    following_ids = [ObjectId(f["following_id"]) for f in await cursor.to_list(length=limit)]

    if not following_ids:
        return []

    users_cursor = db.users.find({"_id": {"$in": following_ids}})
    results = []
    async for u in users_cursor:
        results.append(UserPublicSummary(
            id=str(u["_id"]),
            username=u["username"],
            full_name=u["full_name"],
            avatar_url=u.get("avatar_url")
        ))
    return results

# 6. Create Post
@router.post("/posts", response_model=PostResponse, status_code=status.HTTP_201_CREATED)
async def create_post(
    post_in: PostCreate,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    check_social_post_rate_limit(current_user["id"])

    clean_content = sanitize_text(post_in.content)
    if not clean_content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Post content cannot be empty")

    now = datetime.now(timezone.utc)
    # If media_url is provided, prioritize it, otherwise fall back to image_url
    media_url = post_in.media_url.strip() if post_in.media_url else (post_in.image_url.strip() if post_in.image_url else None)
    media_type = post_in.media_type or ("video" if media_url and any(media_url.lower().endswith(ext) for ext in [".mp4", ".webm", ".ogg", ".mov"]) else "image")

    post_doc = {
        "author_id": current_user["id"],
        "author_username": current_user["username"],
        "author_full_name": current_user["full_name"],
        "author_avatar": current_user.get("avatar_url"),
        "content": clean_content,
        "image_url": media_url if media_type == "image" else None,
        "media_url": media_url,
        "media_type": media_type,
        "likes": [],
        "likes_count": 0,
        "comments_count": 0,
        "is_edited": False,
        "created_at": now,
        "updated_at": now
    }

    res = await db.posts.insert_one(post_doc)
    post_id = str(res.inserted_id)

    return PostResponse(
        id=post_id,
        author_id=current_user["id"],
        author_username=current_user["username"],
        author_full_name=current_user["full_name"],
        author_avatar=current_user.get("avatar_url"),
        content=clean_content,
        image_url=post_doc["image_url"],
        media_url=post_doc["media_url"],
        media_type=post_doc["media_type"],
        created_at=now,
        updated_at=now,
        is_edited=False,
        likes_count=0,
        comments_count=0,
        is_liked=False,
        is_owner=True
    )

# 7. Edit Post
@router.patch("/posts/{post_id}", response_model=PostResponse)
async def edit_post(
    post_id: str,
    update_in: PostUpdate,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    try:
        post_obj = ObjectId(post_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid post ID")

    post = await db.posts.find_one({"_id": post_obj})
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    if post["author_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot edit another user's post")

    clean_content = sanitize_text(update_in.content)
    now = datetime.now(timezone.utc)

    update_fields: dict = {
        "content": clean_content,
        "is_edited": True,
        "updated_at": now
    }
    if update_in.image_url is not None:
        update_fields["image_url"] = update_in.image_url.strip() if update_in.image_url else None
    if update_in.media_url is not None:
        update_fields["media_url"] = update_in.media_url.strip() if update_in.media_url else None
    if update_in.media_type is not None:
        update_fields["media_type"] = update_in.media_type

    await db.posts.update_one({"_id": post_obj}, {"$set": update_fields})
    updated_doc = await db.posts.find_one({"_id": post_obj})

    likes_list = updated_doc.get("likes", [])
    return PostResponse(
        id=post_id,
        author_id=updated_doc["author_id"],
        author_username=updated_doc["author_username"],
        author_full_name=updated_doc["author_full_name"],
        author_avatar=updated_doc.get("author_avatar"),
        content=clean_content,
        image_url=updated_doc.get("image_url"),
        media_url=updated_doc.get("media_url"),
        media_type=updated_doc.get("media_type", "image"),
        created_at=updated_doc["created_at"],
        updated_at=now,
        is_edited=True,
        likes_count=len(likes_list),
        comments_count=updated_doc.get("comments_count", 0),
        is_liked=(current_user["id"] in likes_list),
        is_owner=True
    )

# 8. Delete Post
@router.delete("/posts/{post_id}", status_code=status.HTTP_200_OK)
async def delete_post(
    post_id: str,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    try:
        post_obj = ObjectId(post_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid post ID")

    post = await db.posts.find_one({"_id": post_obj})
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    if post["author_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete another user's post")

    await db.posts.delete_one({"_id": post_obj})
    await db.post_comments.delete_many({"post_id": post_id})

    return {"status": "deleted", "post_id": post_id}

# 9. Get Feed (Global Discovery, Following, or Reels)
@router.get("/feed", response_model=List[PostResponse])
async def get_feed(
    mode: str = Query("discovery", pattern="^(discovery|following|reels)$"),
    limit: int = Query(25, ge=1, le=50),
    before: Optional[str] = Query(None, description="ISO timestamp cursor"),
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    db = get_database()
    if db is None:
        return []

    my_id = current_user["id"] if current_user else None
    query: dict = {}

    if mode == "following":
        if not my_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required for following feed")
        # Find all user IDs current_user follows
        follows_cursor = db.follows.find({"follower_id": my_id})
        followed_ids = [f["following_id"] for f in await follows_cursor.to_list(length=1000)]
        # Include self posts in following feed as well
        followed_ids.append(my_id)
        query["author_id"] = {"$in": followed_ids}
    elif mode == "reels":
        query["media_type"] = "video"
        query["media_url"] = {"$ne": None}

    if before:
        try:
            cursor_dt = datetime.fromisoformat(before)
            query["created_at"] = {"$lt": cursor_dt}
        except Exception:
            pass

    cursor = db.posts.find(query).sort("created_at", -1).limit(limit)
    posts = []
    async for p in cursor:
        likes_list = p.get("likes", [])
        posts.append(PostResponse(
            id=str(p["_id"]),
            author_id=p["author_id"],
            author_username=p["author_username"],
            author_full_name=p["author_full_name"],
            author_avatar=p.get("author_avatar"),
            content=p["content"],
            image_url=p.get("image_url"),
            media_url=p.get("media_url"),
            media_type=p.get("media_type", "image"),
            created_at=p["created_at"],
            updated_at=p.get("updated_at", p["created_at"]),
            is_edited=p.get("is_edited", False),
            likes_count=len(likes_list),
            comments_count=p.get("comments_count", 0),
            is_liked=(my_id in likes_list) if my_id else False,
            is_owner=(my_id == p["author_id"]) if my_id else False
        ))

    return posts

# 10. Get User Posts
@router.get("/users/{user_id}/posts", response_model=List[PostResponse])
async def get_user_posts(
    user_id: str,
    media_filter: Optional[str] = Query(None, pattern="^(image|video)$"),
    limit: int = Query(25, ge=1, le=50),
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    db = get_database()
    if db is None:
        return []

    my_id = current_user["id"] if current_user else None
    query: dict = {"author_id": user_id}
    if media_filter:
        query["media_type"] = media_filter
        query["media_url"] = {"$ne": None}

    cursor = db.posts.find(query).sort("created_at", -1).limit(limit)

    posts = []
    async for p in cursor:
        likes_list = p.get("likes", [])
        posts.append(PostResponse(
            id=str(p["_id"]),
            author_id=p["author_id"],
            author_username=p["author_username"],
            author_full_name=p["author_full_name"],
            author_avatar=p.get("author_avatar"),
            content=p["content"],
            image_url=p.get("image_url"),
            media_url=p.get("media_url"),
            media_type=p.get("media_type", "image"),
            created_at=p["created_at"],
            updated_at=p.get("updated_at", p["created_at"]),
            is_edited=p.get("is_edited", False),
            likes_count=len(likes_list),
            comments_count=p.get("comments_count", 0),
            is_liked=(my_id in likes_list) if my_id else False,
            is_owner=(my_id == p["author_id"]) if my_id else False
        ))

    return posts

# 11. Like Post
@router.post("/posts/{post_id}/like", status_code=status.HTTP_200_OK)
async def like_post(
    post_id: str,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    try:
        post_obj = ObjectId(post_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid post ID")

    my_id = current_user["id"]
    # Atomic $addToSet prevents duplicate likes
    res = await db.posts.update_one(
        {"_id": post_obj},
        {"$addToSet": {"likes": my_id}}
    )

    if res.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    post = await db.posts.find_one({"_id": post_obj})
    likes_count = len(post.get("likes", []))
    await db.posts.update_one({"_id": post_obj}, {"$set": {"likes_count": likes_count}})

    # Trigger notification if someone else liked the post and this was a new like
    if res.modified_count > 0 and post.get("author_id") != my_id:
        from app.services.notification_service import create_event_notification
        snippet = post.get("content", "")[:60]
        await create_event_notification(
            recipient_user_id=post["author_id"],
            actor_user_id=my_id,
            category="social",
            event_type="social_like",
            title=f"{current_user['full_name']} liked your post",
            desc=f'"{snippet}..."' if len(post.get("content", "")) > 60 else f'"{snippet}"',
            navigation_target=f"social:post:{post_id}",
            metadata={"post_id": post_id, "liker_username": current_user["username"]},
            event_id=f"like_{post_id}_{my_id}"
        )

    return {"status": "liked", "post_id": post_id, "likes_count": likes_count}

# 12. Unlike Post
@router.delete("/posts/{post_id}/like", status_code=status.HTTP_200_OK)
async def unlike_post(
    post_id: str,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    try:
        post_obj = ObjectId(post_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid post ID")

    my_id = current_user["id"]
    res = await db.posts.update_one(
        {"_id": post_obj},
        {"$pull": {"likes": my_id}}
    )

    if res.matched_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    post = await db.posts.find_one({"_id": post_obj})
    likes_count = len(post.get("likes", []))
    await db.posts.update_one({"_id": post_obj}, {"$set": {"likes_count": likes_count}})

    return {"status": "unliked", "post_id": post_id, "likes_count": likes_count}

# 13. Create Comment
@router.post("/posts/{post_id}/comments", response_model=CommentResponse, status_code=status.HTTP_201_CREATED)
async def create_comment(
    post_id: str,
    comment_in: CommentCreate,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    check_comment_rate_limit(current_user["id"])

    try:
        post_obj = ObjectId(post_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid post ID")

    post = await db.posts.find_one({"_id": post_obj})
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    clean_content = sanitize_text(comment_in.content)
    now = datetime.now(timezone.utc)

    comment_doc = {
        "post_id": post_id,
        "author_id": current_user["id"],
        "author_username": current_user["username"],
        "author_full_name": current_user["full_name"],
        "author_avatar": current_user.get("avatar_url"),
        "content": clean_content,
        "created_at": now
    }

    res = await db.post_comments.insert_one(comment_doc)
    comment_id = str(res.inserted_id)

    # Increment comments_count on post atomically
    await db.posts.update_one({"_id": post_obj}, {"$inc": {"comments_count": 1}})

    # Trigger notification if commenter is not post author
    if post.get("author_id") != current_user["id"]:
        from app.services.notification_service import create_event_notification
        await create_event_notification(
            recipient_user_id=post["author_id"],
            actor_user_id=current_user["id"],
            category="social",
            event_type="social_comment",
            title=f"{current_user['full_name']} commented on your post",
            desc=clean_content[:100] + ("..." if len(clean_content) > 100 else ""),
            navigation_target=f"social:post:{post_id}",
            metadata={"post_id": post_id, "comment_id": comment_id, "commenter_username": current_user["username"]},
            event_id=f"comment_{comment_id}"
        )

    return CommentResponse(
        id=comment_id,
        post_id=post_id,
        author_id=current_user["id"],
        author_username=current_user["username"],
        author_full_name=current_user["full_name"],
        author_avatar=current_user.get("avatar_url"),
        content=clean_content,
        created_at=now,
        is_owner=True
    )

# 14. List Comments for Post
@router.get("/posts/{post_id}/comments", response_model=List[CommentResponse])
async def list_comments(
    post_id: str,
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        return []

    my_id = current_user["id"]
    cursor = db.post_comments.find({"post_id": post_id}).sort("created_at", 1).limit(limit)

    comments = []
    async for c in cursor:
        comments.append(CommentResponse(
            id=str(c["_id"]),
            post_id=c["post_id"],
            author_id=c["author_id"],
            author_username=c["author_username"],
            author_full_name=c["author_full_name"],
            author_avatar=c.get("author_avatar"),
            content=c["content"],
            created_at=c["created_at"],
            is_owner=(my_id == c["author_id"])
        ))

    return comments

# 15. Delete Comment
@router.delete("/comments/{comment_id}", status_code=status.HTTP_200_OK)
async def delete_comment(
    comment_id: str,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    try:
        comm_obj = ObjectId(comment_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid comment ID")

    comment = await db.post_comments.find_one({"_id": comm_obj})
    if not comment:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Comment not found")

    # Authorize: either comment author or post author can delete the comment
    post = await db.posts.find_one({"_id": ObjectId(comment["post_id"])})
    is_post_owner = post and (post["author_id"] == current_user["id"])
    is_comment_owner = comment["author_id"] == current_user["id"]

    if not (is_comment_owner or is_post_owner):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this comment")

    await db.post_comments.delete_one({"_id": comm_obj})
    if post:
        await db.posts.update_one({"_id": post["_id"]}, {"$inc": {"comments_count": -1}})

    return {"status": "deleted", "comment_id": comment_id}

# 16. Report Content
@router.post("/reports", response_model=ReportResponse, status_code=status.HTTP_201_CREATED)
async def report_content(
    report_in: ReportCreate,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    my_id = current_user["id"]
    check_report_rate_limit(my_id)

    # Prevent spamming multiple reports on the exact same target by the same reporter
    existing = await db.reports.find_one({
        "reporter_id": my_id,
        "target_type": report_in.target_type,
        "target_id": report_in.target_id
    })
    if existing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You have already submitted a report for this content")

    now = datetime.now(timezone.utc)
    report_doc = {
        "reporter_id": my_id,
        "target_type": report_in.target_type,
        "target_id": report_in.target_id,
        "reason": sanitize_text(report_in.reason),
        "description": sanitize_text(report_in.description) if report_in.description else None,
        "status": "pending",
        "created_at": now
    }

    res = await db.reports.insert_one(report_doc)
    return ReportResponse(
        id=str(res.inserted_id),
        reporter_id=my_id,
        target_type=report_in.target_type,
        target_id=report_in.target_id,
        reason=report_doc["reason"],
        status="pending",
        created_at=now
    )

# 17. Upload Social Post Media (Image or Video)
@router.post("/media", status_code=status.HTTP_201_CREATED)
async def upload_social_media(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user)
):
    check_social_post_rate_limit(current_user["id"])

    content_type = (file.content_type or "").lower().split(";")[0].strip()
    is_video = content_type in ALLOWED_VIDEO_MIMES
    is_image = content_type in ALLOWED_IMAGE_MIMES

    if not (is_image or is_video):
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Unsupported media type '{content_type}'. Allowed: JPEG, PNG, WebP, GIF, MP4, WebM, OGG, QuickTime"
        )

    ext = ALLOWED_VIDEO_MIMES[content_type] if is_video else ALLOWED_IMAGE_MIMES[content_type]
    random_filename = f"{uuid.uuid4().hex}{ext}"
    quarantine_path = os.path.join(QUARANTINE_DIR, f"quarantine_{random_filename}")
    dest_path = os.path.join(MEDIA_STORAGE_DIR, random_filename)

    total_bytes = 0
    header_checked = False

    try:
        async with aiofiles.open(quarantine_path, "wb") as out_file:
            while True:
                chunk = await file.read(CHUNK_SIZE)
                if not chunk:
                    break

                if not header_checked:
                    if not verify_media_magic(chunk[:32], is_video):
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Uploaded file signature does not match the declared media format"
                        )
                    header_checked = True

                total_bytes += len(chunk)
                if total_bytes > MAX_MEDIA_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail=f"Media file exceeds maximum allowed size of {MAX_MEDIA_SIZE // (1024 * 1024)}MB"
                    )

                await out_file.write(chunk)

        # Malware scan before promotion
        is_clean, scan_msg = await scan_quarantined_media(quarantine_path, file.filename or random_filename)
        if not is_clean:
            if os.path.exists(quarantine_path):
                try:
                    os.remove(quarantine_path)
                except Exception:
                    pass
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=scan_msg)

        # Atomic promotion from quarantine to media storage
        os.replace(quarantine_path, dest_path)

    except HTTPException:
        if os.path.exists(quarantine_path):
            try:
                os.remove(quarantine_path)
            except Exception:
                pass
        raise
    except Exception as e:
        if os.path.exists(quarantine_path):
            try:
                os.remove(quarantine_path)
            except Exception:
                pass
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Storage error: {str(e)}")

    media_url = f"/api/v1/social/media/{random_filename}"
    media_type = "video" if is_video else "image"

    return {
        "media_url": media_url,
        "media_type": media_type,
        "filename": random_filename,
        "size_bytes": total_bytes
    }

# 18. Stream / Serve Social Media
@router.get("/media/{filename}")
async def get_social_media(filename: str):
    # Prevent directory traversal attacks
    safe_filename = os.path.basename(filename)
    if safe_filename != filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filename")

    file_path = os.path.join(MEDIA_STORAGE_DIR, safe_filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media file not found")

    file_size = os.path.getsize(file_path)
    ext = os.path.splitext(safe_filename)[1].lower()
    
    # Map extension to mime
    mime = "application/octet-stream"
    for m, e in {**ALLOWED_IMAGE_MIMES, **ALLOWED_VIDEO_MIMES}.items():
        if e == ext:
            mime = m
            break

    async def file_generator():
        async with aiofiles.open(file_path, mode="rb") as f:
            while chunk := await f.read(CHUNK_SIZE):
                yield chunk

    headers = {
        "Content-Length": str(file_size),
        "Content-Type": mime,
        "Accept-Ranges": "bytes",
        "Cache-Control": "public, max-age=86400"
    }
    return StreamingResponse(file_generator(), headers=headers, media_type=mime)
