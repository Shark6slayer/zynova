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
    UserPublicSummary,
    StoryCreate,
    StoryReactionCreate,
    StoryGroupResponse,
    StoryHighlightCreate,
    StoryHighlightResponse,
    SocialNoteCreate,
    SocialNoteResponse,
    VerificationApplicationCreate,
    VerificationApplicationResponse
)
from app.api.deps import get_current_user, get_optional_current_user
from app.database.client import get_database
from app.services.identity_service import is_blocked, get_blocked_users, get_all_blocked_user_ids
from app.services.social_service import (
    extract_hashtags,
    request_follow_user,
    respond_to_follow_request,
    remove_follower,
    get_suggested_accounts,
    create_story,
    get_stories_feed,
    record_story_view,
    add_story_reaction,
    create_story_highlight,
    get_user_highlights,
    post_social_note,
    get_following_notes,
    toggle_post_bookmark,
    get_bookmarked_posts,
    get_explore_feed,
    get_posts_by_hashtag,
    submit_verification_application,
    review_verification_application
)
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

    my_id = current_user["id"] if current_user else None
    if my_id and my_id != user_id:
        if await is_blocked(db, my_id, user_id):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User profile unavailable")

    followers_count = await db.follows.count_documents({"following_id": user_id})
    following_count = await db.follows.count_documents({"follower_id": user_id})
    posts_count = await db.posts.count_documents({"author_id": user_id})

    # Check if current user is following target user or has pending request
    is_following = False
    has_pending = False
    if my_id and my_id != user_id:
        existing_follow = await db.follows.find_one({
            "follower_id": my_id,
            "following_id": user_id
        })
        is_following = existing_follow is not None
        if not is_following:
            pending_req = await db.follow_requests.find_one({
                "sender_id": my_id,
                "target_id": user_id,
                "status": "pending"
            })
            has_pending = pending_req is not None

    social_profile = target_user.get("social_profile", {})

    return SocialProfileResponse(
        id=user_id,
        username=target_user["username"],
        full_name=target_user["full_name"],
        avatar_url=target_user.get("avatar_url"),
        bio=target_user.get("bio"),
        website=social_profile.get("website"),
        is_private=social_profile.get("is_private", False),
        is_verified=social_profile.get("is_verified", False),
        created_at=target_user.get("created_at", datetime.now(timezone.utc)),
        followers_count=followers_count,
        following_count=following_count,
        posts_count=posts_count,
        is_following=is_following,
        has_pending_follow_request=has_pending,
        is_self=(my_id == user_id) if my_id else False
    )

# 2. Follow User (Handles public auto-follow vs private request)
@router.post("/profiles/{user_id}/follow", status_code=status.HTTP_200_OK)
async def follow_user(
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    return await request_follow_user(db, current_user, user_id)

# 2b. Follow Request Response (Accept or Reject)
@router.post("/follow-requests/{sender_id}/respond", status_code=status.HTTP_200_OK)
async def handle_follow_request(
    sender_id: str,
    action: str = Query(..., pattern="^(accept|reject)$"),
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    return await respond_to_follow_request(db, current_user["id"], sender_id, action)

# 2c. Remove Follower
@router.delete("/followers/{follower_id}", status_code=status.HTTP_200_OK)
async def remove_follower_endpoint(
    follower_id: str,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    return await remove_follower(db, current_user["id"], follower_id)

# 2d. Suggested Accounts
@router.get("/suggested", response_model=List[dict])
async def list_suggested_accounts(
    limit: int = Query(10, ge=1, le=30),
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        return []

    return await get_suggested_accounts(db, current_user["id"], limit)

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

    from app.services.moderation_service import (
        check_user_safety_restriction,
        evaluate_text_content,
        compute_content_hash,
        check_duplicate_spam_burst,
        record_moderation_decision,
        enqueue_media_moderation,
    )
    restr_msg = await check_user_safety_restriction(db, current_user["id"], "post")
    if restr_msg:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=restr_msg)

    clean_content = sanitize_text(post_in.content)
    if not clean_content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Post content cannot be empty")

    if await check_duplicate_spam_burst(db, current_user["id"], compute_content_hash(clean_content)):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail="Duplicate spam burst detected. Please wait before posting identical content.")

    mod_eval = evaluate_text_content(clean_content, context="post")
    mod_status = "quarantined" if mod_eval["decision"] in {"ESCALATE", "RESTRICT"} else "active"

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
        "moderation_status": mod_status,
        "moderation_score": mod_eval["severity_score"],
        "created_at": now,
        "updated_at": now
    }

    res = await db.posts.insert_one(post_doc)
    post_id = str(res.inserted_id)

    if mod_eval["decision"] != "ALLOW":
        await record_moderation_decision(db, "post", post_id, current_user["id"], mod_eval, reason="automated_text_policy_screening")
    if media_url:
        await enqueue_media_moderation(db, "reel" if media_type == "video" else "post", post_id, current_user["id"], media_type, caption=clean_content)

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

# 8b. Archive Post
@router.post("/posts/{post_id}/archive", status_code=status.HTTP_200_OK)
async def archive_post(
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot archive another user's post")

    await db.posts.update_one({"_id": post_obj}, {"$set": {"is_archived": True, "archived_at": datetime.now(timezone.utc)}})
    return {"status": "archived", "post_id": post_id}

# 8c. Unarchive Post
@router.post("/posts/{post_id}/unarchive", status_code=status.HTTP_200_OK)
async def unarchive_post(
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
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot unarchive another user's post")

    await db.posts.update_one({"_id": post_obj}, {"$set": {"is_archived": False}, "$unset": {"archived_at": ""}})
    return {"status": "unarchived", "post_id": post_id}

# 8d. Get Archived Posts
@router.get("/posts/archived", response_model=List[PostResponse])
async def get_archived_posts(
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        return []

    my_id = current_user["id"]
    cursor = db.posts.find({"author_id": my_id, "is_archived": True}).sort("created_at", -1)
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
            media_assets=p.get("media_assets", []),
            tags=p.get("tags", []),
            location=p.get("location"),
            created_at=p["created_at"],
            updated_at=p.get("updated_at", p["created_at"]),
            is_edited=p.get("is_edited", False),
            likes_count=len(likes_list),
            comments_count=p.get("comments_count", 0),
            is_liked=(my_id in likes_list),
            is_owner=True
        ))
    return posts

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

    # Mutual blocking isolation: hide posts from blocked/blocking users
    if my_id:
        blocked_ids = await get_all_blocked_user_ids(db, my_id)
        if blocked_ids:
            query["author_id"] = {"$nin": list(blocked_ids)}

    if mode == "following":
        if not my_id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required for following feed")
        # Find all user IDs current_user follows
        follows_cursor = db.follows.find({"follower_id": my_id})
        followed_ids = [f["following_id"] for f in await follows_cursor.to_list(length=1000)]
        followed_ids.append(my_id)
        # Apply blocking filter to followed list
        if my_id and blocked_ids:
            followed_ids = [uid for uid in followed_ids if uid not in blocked_ids]
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

    # Exclude posts from accounts pending deletion or inactive, archived, or moderated/quarantined posts
    query["account_status"] = {"$ne": "pending_deletion"}
    query["is_archived"] = {"$ne": True}
    query["moderation_status"] = {"$nin": ["removed", "restricted", "quarantined"]}
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
            media_assets=p.get("media_assets", []),
            tags=p.get("tags", []),
            location=p.get("location"),
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
    if my_id and my_id != user_id:
        if await is_blocked(db, my_id, user_id):
            return []

    # Check if target account is private and viewer is not following
    target_user = await db.users.find_one({"_id": ObjectId(user_id)})
    if target_user and target_user.get("social_profile", {}).get("is_private", False):
        if my_id != user_id:
            is_follower = await db.follows.find_one({"follower_id": my_id, "following_id": user_id}) if my_id else False
            if not is_follower:
                return []

    query: dict = {"author_id": user_id}
    if media_filter:
        query["media_type"] = media_filter
        query["media_url"] = {"$ne": None}

    # Exclude posts from accounts pending deletion or inactive, archived, or moderated/quarantined posts
    query["account_status"] = {"$ne": "pending_deletion"}
    query["is_archived"] = {"$ne": True}
    query["moderation_status"] = {"$nin": ["removed", "restricted", "quarantined"]}
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
            media_assets=p.get("media_assets", []),
            tags=p.get("tags", []),
            location=p.get("location"),
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
    post = await db.posts.find_one({"_id": post_obj})
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    # Mutual block check: cannot interact with posts from blocked/blocking users
    if await is_blocked(db, my_id, post["author_id"]):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    # Atomic $addToSet prevents duplicate likes
    res = await db.posts.update_one(
        {"_id": post_obj},
        {"$addToSet": {"likes": my_id}}
    )

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

    # Mutual block check: cannot comment on post if viewer has blocked author OR author has blocked viewer
    if await is_blocked(db, current_user["id"], post["author_id"]):
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

    try:
        post_obj = ObjectId(post_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid post ID")

    post = await db.posts.find_one({"_id": post_obj})
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    my_id = current_user["id"]
    if await is_blocked(db, my_id, post["author_id"]):
        return []

    blocked_uids = await get_all_blocked_user_ids(db, my_id)
    query: dict = {"post_id": post_id}
    if blocked_uids:
        query["author_id"] = {"$nin": list(blocked_uids)}

    cursor = db.post_comments.find(query).sort("created_at", 1).limit(limit)

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

# ---------------------------------------------------------------------------
# Phase 25 Social Platform Additions: Stories, Highlights, Notes & Verification
# ---------------------------------------------------------------------------

# 19. Create 24-Hour Ephemeral Story
@router.post("/stories", status_code=status.HTTP_201_CREATED)
async def post_story(
    story_in: StoryCreate,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    check_social_post_rate_limit(current_user["id"])
    return await create_story(
        db=db,
        author=current_user,
        media_url=story_in.media_url,
        media_type=story_in.media_type,
        caption=story_in.caption,
        is_close_friends_only=story_in.is_close_friends_only
    )

# 20. Get Stories Feed (Grouped by followed users + self)
@router.get("/stories/feed", response_model=List[StoryGroupResponse])
async def list_stories_feed(
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        return []

    return await get_stories_feed(db, current_user["id"])

# 21. Record Story View
@router.post("/stories/{story_id}/view", status_code=status.HTTP_200_OK)
async def view_story(
    story_id: str,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    return await record_story_view(db, story_id, current_user["id"])

# 22. React to Story
@router.post("/stories/{story_id}/react", status_code=status.HTTP_200_OK)
async def react_to_story(
    story_id: str,
    reaction_in: StoryReactionCreate,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    return await add_story_reaction(db, story_id, current_user["id"], reaction_in.reaction)

# 23. Story Highlights
@router.post("/highlights", status_code=status.HTTP_201_CREATED)
async def create_highlight(
    highlight_in: StoryHighlightCreate,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    return await create_story_highlight(
        db=db,
        author_id=current_user["id"],
        title=highlight_in.title,
        story_ids=highlight_in.story_ids,
        cover_image_url=highlight_in.cover_image_url
    )

@router.get("/users/{user_id}/highlights", response_model=List[dict])
async def list_user_highlights(
    user_id: str,
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    db = get_database()
    if db is None:
        return []

    viewer_id = current_user["id"] if current_user else None
    return await get_user_highlights(db, user_id, viewer_id)

# 24. Social Notes (60-character status expiring in 24h)
@router.post("/notes", status_code=status.HTTP_201_CREATED)
async def post_note(
    note_in: SocialNoteCreate,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    return await post_social_note(
        db=db,
        user=current_user,
        text=note_in.text,
        music_title=note_in.music_title,
        music_artist=note_in.music_artist
    )

@router.get("/notes", response_model=List[SocialNoteResponse])
async def list_notes(
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        return []

    return await get_following_notes(db, current_user["id"])

# 25. Bookmark / Save Post Toggle
@router.post("/posts/{post_id}/bookmark", status_code=status.HTTP_200_OK)
async def bookmark_post(
    post_id: str,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    return await toggle_post_bookmark(db, post_id, current_user["id"])

# 26. Get Bookmarked Posts
@router.get("/bookmarks", response_model=List[PostResponse])
async def list_bookmarks(
    limit: int = Query(25, ge=1, le=50),
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        return []

    bookmarked_data = await get_bookmarked_posts(db, current_user["id"], limit)
    responses = []
    for p in bookmarked_data:
        responses.append(PostResponse(
            id=p["id"],
            author_id=p["author_id"],
            author_username=p["author_username"],
            author_full_name=p["author_full_name"],
            author_avatar=p.get("author_avatar"),
            content=p["content"],
            image_url=p.get("image_url"),
            media_url=p.get("media_url"),
            media_type=p.get("media_type", "image"),
            media_assets=p.get("media_assets", []),
            tags=p.get("tags", []),
            location=p.get("location"),
            created_at=p["created_at"],
            updated_at=p["created_at"],
            is_edited=False,
            likes_count=p.get("likes_count", 0),
            comments_count=p.get("comments_count", 0),
            is_liked=False,
            is_bookmarked=True,
            is_owner=(p["author_id"] == current_user["id"])
        ))
    return responses

# 27. Explore Feed (Ranked engagement discovery)
@router.get("/explore", response_model=List[PostResponse])
async def explore_posts(
    limit: int = Query(30, ge=1, le=60),
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    db = get_database()
    if db is None:
        return []

    my_id = current_user["id"] if current_user else None
    explore_data = await get_explore_feed(db, my_id, limit)

    responses = []
    for p in explore_data:
        responses.append(PostResponse(
            id=p["id"],
            author_id=p["author_id"],
            author_username=p["author_username"],
            author_full_name=p["author_full_name"],
            author_avatar=p.get("author_avatar"),
            content=p["content"],
            image_url=p.get("image_url"),
            media_url=p.get("media_url"),
            media_type=p.get("media_type", "image"),
            media_assets=p.get("media_assets", []),
            tags=p.get("tags", []),
            location=p.get("location"),
            created_at=p["created_at"],
            updated_at=p["created_at"],
            is_edited=False,
            likes_count=p.get("likes_count", 0),
            comments_count=p.get("comments_count", 0),
            is_liked=p.get("is_liked", False),
            is_bookmarked=False,
            is_owner=(p["author_id"] == my_id) if my_id else False
        ))
    return responses

# 28. Hashtag Posts Filter
@router.get("/tags/{tag}", response_model=List[PostResponse])
async def get_tag_posts(
    tag: str,
    limit: int = Query(25, ge=1, le=50),
    current_user: Optional[dict] = Depends(get_optional_current_user)
):
    db = get_database()
    if db is None:
        return []

    my_id = current_user["id"] if current_user else None
    tag_data = await get_posts_by_hashtag(db, tag, my_id, limit)

    responses = []
    for p in tag_data:
        responses.append(PostResponse(
            id=p["id"],
            author_id=p["author_id"],
            author_username=p["author_username"],
            author_full_name=p["author_full_name"],
            author_avatar=p.get("author_avatar"),
            content=p["content"],
            image_url=p.get("image_url"),
            media_url=p.get("media_url"),
            media_type=p.get("media_type", "image"),
            media_assets=p.get("media_assets", []),
            tags=p.get("tags", []),
            location=p.get("location"),
            created_at=p["created_at"],
            updated_at=p["created_at"],
            is_edited=False,
            likes_count=p.get("likes_count", 0),
            comments_count=p.get("comments_count", 0),
            is_liked=p.get("is_liked", False),
            is_bookmarked=False,
            is_owner=(p["author_id"] == my_id) if my_id else False
        ))
    return responses

# 29. Verified Badge Application (Module 10)
@router.post("/verification/apply", status_code=status.HTTP_201_CREATED)
async def apply_for_verification(
    app_in: VerificationApplicationCreate,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    return await submit_verification_application(db, current_user["id"], app_in.model_dump())

@router.post("/verification/{app_id}/review", status_code=status.HTTP_200_OK)
async def review_verification(
    app_id: str,
    action: str = Query(..., pattern="^(approve|reject)$"),
    notes: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    # Only admin roles authorized
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin authorization required to review verification applications")

    return await review_verification_application(db, app_id, current_user["id"], action, notes)


# --------------------------------------------------------------------------
# 30. ZenoSocial Direct Messaging (Zen_ID Identity & 3-Message Non-Mutual Limit)
# --------------------------------------------------------------------------
from pydantic import BaseModel as _SocialBaseModel
from pymongo import ReturnDocument

NON_MUTUAL_MESSAGE_LIMIT = 3


class SocialSendMessageRequest(_SocialBaseModel):
    recipient_zen_id: str
    text: str
    reply_to_message_id: Optional[str] = None


class SocialShareContentRequest(_SocialBaseModel):
    recipient_zen_ids: List[str]
    content_type: str
    content_id: str
    message: Optional[str] = None


async def _is_mutual_follow(db, user_a_id: str, user_b_id: str) -> bool:
    a_to_b = await db.follows.find_one({"follower_id": user_a_id, "following_id": user_b_id}, {"_id": 1})
    if not a_to_b:
        return False
    b_to_a = await db.follows.find_one({"follower_id": user_b_id, "following_id": user_a_id}, {"_id": 1})
    return b_to_a is not None


async def _resolve_user_by_zen_id(db, zen_id: str) -> Optional[dict]:
    clean = zen_id.strip().lstrip("@").lower()
    if clean.startswith("zen_"):
        clean = clean[4:]
    return await db.users.find_one(
        {"$or": [{"zen_id": clean}, {"username": clean}, {"zen_id": f"zen_{clean}"}]},
        {"_id": 1, "username": 1, "zen_id": 1, "full_name": 1, "avatar_url": 1, "is_verified": 1},
    )


async def _dispatch_social_message(
    db,
    sender: dict,
    recipient: dict,
    text: str,
    shared_content: Optional[dict] = None,
) -> dict:
    sender_id = sender["id"]
    recipient_id = str(recipient["_id"])
    if sender_id == recipient_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot message yourself")

    if await is_blocked(db, sender_id, recipient_id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot message a blocked user")

    from app.services.moderation_service import (
        check_user_safety_restriction,
        evaluate_text_content,
        record_moderation_decision,
    )
    restr_msg = await check_user_safety_restriction(db, sender_id, "message")
    if restr_msg:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=restr_msg)

    msg_eval = evaluate_text_content(text, context="social_message")
    if msg_eval["decision"] in {"ESCALATE", "RESTRICT"}:
        await record_moderation_decision(db, "social_message", f"{sender_id}_{recipient_id}", sender_id, msg_eval, reason="social_message_safety_block")
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message blocked by safety policy (malicious link or abusive content detected).")

    is_mutual = await _is_mutual_follow(db, sender_id, recipient_id)
    now = datetime.now(timezone.utc)
    p_ids = sorted([sender_id, recipient_id])
    p_key = "_".join(p_ids)

    sender_zen = sender.get("zen_id") or sender.get("username")
    recipient_zen = recipient.get("zen_id") or recipient.get("username")

    # Ensure unique index on participant_key and upsert atomically
    try:
        await db.social_conversations.create_index("participant_key", unique=True)
    except Exception:
        pass
    try:
        await db.social_conversations.update_one(
            {"participant_key": p_key},
            {
                "$setOnInsert": {
                    "participant_key": p_key,
                    "participant_ids": p_ids,
                    "participant_zen_ids": [sender_zen, recipient_zen],
                    "sent_counts": {sender_id: 0, recipient_id: 0},
                    "created_at": now,
                    "updated_at": now,
                }
            },
            upsert=True,
        )
    except DuplicateKeyError:
        pass

    if is_mutual:
        conv = await db.social_conversations.find_one_and_update(
            {"participant_key": p_key},
            {"$inc": {f"sent_counts.{sender_id}": 1}, "$set": {"updated_at": now}},
            return_document=ReturnDocument.AFTER,
        )
    else:
        # Atomic compare-and-increment enforcing strict 3-message cap under concurrency
        conv = await db.social_conversations.find_one_and_update(
            {
                "participant_key": p_key,
                "$or": [
                    {f"sent_counts.{sender_id}": {"$lt": NON_MUTUAL_MESSAGE_LIMIT}},
                    {f"sent_counts.{sender_id}": {"$exists": False}},
                ],
            },
            {"$inc": {f"sent_counts.{sender_id}": 1}, "$set": {"updated_at": now}},
            return_document=ReturnDocument.AFTER,
        )
        if conv is None:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Message limit reached (3/3). Recipient must follow you back to continue messaging.",
            )

    conv_id = str(conv["_id"])
    msg_doc = {
        "conversation_id": conv_id,
        "sender_id": sender_id,
        "sender_zen_id": sender_zen,
        "recipient_id": recipient_id,
        "recipient_zen_id": recipient_zen,
        "text": sanitize_text(text),
        "shared_content": shared_content,
        "status": "sent",
        "created_at": now,
    }
    res = await db.social_messages.insert_one(msg_doc)
    msg_id = str(res.inserted_id)

    await db.social_conversations.update_one(
        {"_id": conv["_id"]},
        {
            "$set": {
                "last_message": {
                    "id": msg_id,
                    "sender_id": sender_id,
                    "sender_zen_id": sender_zen,
                    "text": msg_doc["text"],
                    "created_at": now,
                },
                "updated_at": now,
            }
        },
    )

    return {
        "id": msg_id,
        "conversation_id": conv_id,
        "sender_id": sender_id,
        "sender_zen_id": sender_zen,
        "recipient_id": recipient_id,
        "recipient_zen_id": recipient_zen,
        "text": msg_doc["text"],
        "shared_content": shared_content,
        "status": "sent",
        "created_at": now.isoformat(),
    }


@router.get("/messages/conversations")
async def list_social_conversations(
    limit: int = Query(20, ge=1, le=50),
    current_user: dict = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        return []
    my_id = current_user["id"]
    blocked_ids = await get_all_blocked_user_ids(db, my_id)
    cursor = db.social_conversations.find({"participant_ids": my_id}).sort("updated_at", -1).limit(limit)
    results = []
    async for conv in cursor:
        others = [p for p in conv.get("participant_ids", []) if p != my_id]
        if not others or others[0] in blocked_ids:
            continue
        other_id = others[0]
        other_doc = await db.users.find_one({"_id": ObjectId(other_id)}, {"username": 1, "zen_id": 1, "full_name": 1, "avatar_url": 1, "is_verified": 1})
        if not other_doc:
            continue
        is_mutual = await _is_mutual_follow(db, my_id, other_id)
        sent_by_me = conv.get("sent_counts", {}).get(my_id, 0)
        remaining = max(0, NON_MUTUAL_MESSAGE_LIMIT - sent_by_me) if not is_mutual else 999999
        results.append({
            "id": str(conv["_id"]),
            "participant_ids": conv.get("participant_ids", []),
            "participant_zen_ids": conv.get("participant_zen_ids", []),
            "other_participant": {
                "id": other_id,
                "username": other_doc.get("zen_id") or other_doc.get("username"),
                "full_name": other_doc.get("full_name", ""),
                "avatar_url": other_doc.get("avatar_url"),
                "is_verified": other_doc.get("is_verified", False),
            },
            "is_mutual_follow": is_mutual,
            "messages_sent_by_me": sent_by_me,
            "remaining_messages_allowed": remaining,
            "can_send_message": is_mutual or sent_by_me < NON_MUTUAL_MESSAGE_LIMIT,
            "last_message": conv.get("last_message"),
            "unread_count": 0,
            "updated_at": conv.get("updated_at").isoformat() if conv.get("updated_at") else "",
        })
    return results


@router.get("/messages/conversations/{conv_id}/messages")
async def get_social_messages(
    conv_id: str,
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    if not ObjectId.is_valid(conv_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid conversation ID")
    conv = await db.social_conversations.find_one({"_id": ObjectId(conv_id)})
    my_id = current_user["id"]
    if not conv or my_id not in conv.get("participant_ids", []):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    others = [p for p in conv.get("participant_ids", []) if p != my_id]
    other_id = others[0] if others else my_id
    if await is_blocked(db, my_id, other_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    is_mutual = await _is_mutual_follow(db, my_id, other_id)
    sent_by_me = conv.get("sent_counts", {}).get(my_id, 0)
    remaining = max(0, NON_MUTUAL_MESSAGE_LIMIT - sent_by_me) if not is_mutual else 999999

    cursor = db.social_messages.find({"conversation_id": conv_id}).sort("created_at", 1).limit(limit)
    messages = []
    async for m in cursor:
        messages.append({
            "id": str(m["_id"]),
            "conversation_id": conv_id,
            "sender_id": m["sender_id"],
            "sender_zen_id": m["sender_zen_id"],
            "recipient_id": m["recipient_id"],
            "recipient_zen_id": m["recipient_zen_id"],
            "text": m["text"],
            "shared_content": m.get("shared_content"),
            "status": m.get("status", "sent"),
            "created_at": m["created_at"].isoformat(),
        })

    return {
        "conversation_id": conv_id,
        "is_mutual_follow": is_mutual,
        "messages_sent_by_me": sent_by_me,
        "remaining_messages_allowed": remaining,
        "can_send_message": is_mutual or sent_by_me < NON_MUTUAL_MESSAGE_LIMIT,
        "non_mutual_limit": NON_MUTUAL_MESSAGE_LIMIT,
        "messages": messages,
    }


@router.post("/messages/send", status_code=status.HTTP_201_CREATED)
async def send_social_message(
    body: SocialSendMessageRequest,
    current_user: dict = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    recipient = await _resolve_user_by_zen_id(db, body.recipient_zen_id)
    if not recipient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient Zen_ID not found")
    return await _dispatch_social_message(db, current_user, recipient, body.text)


@router.post("/messages/share-content", status_code=status.HTTP_201_CREATED)
async def share_social_content(
    body: SocialShareContentRequest,
    current_user: dict = Depends(get_current_user),
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")
    shared_meta = {
        "type": body.content_type,
        "content_id": body.content_id,
        "creator_zen_id": current_user.get("zen_id") or current_user.get("username"),
        "caption_snippet": (body.message or f"Shared {body.content_type}")[:120],
    }
    sent_messages = []
    for r_zen in body.recipient_zen_ids:
        recipient = await _resolve_user_by_zen_id(db, r_zen)
        if not recipient:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Recipient {r_zen} not found")
        msg = await _dispatch_social_message(
            db, current_user, recipient, body.message or f"Shared a {body.content_type}", shared_content=shared_meta
        )
        sent_messages.append(msg)
    return sent_messages
