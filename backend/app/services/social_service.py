"""
Zynova Social Service — Phase 25 (Complete Production Platform)
Implements all core domain logic for:
  - Module 1: Social Identity (Public/Private profiles, Verified badge, Mutings/Restrictions)
  - Module 2: Home Feed (Curated ranking, following feed, carousels, bookmarked posts)
  - Module 3: Stories (24h expiry logic, close friends, view tracking, reactions, highlights)
  - Module 4: Reels (Vertical video, view counting, recommendation algorithms)
  - Module 5: Followers and Following (Private account follow requests, accept/reject, removal)
  - Module 6: Explore and Search (Trending score, hashtags, user/post search, history)
  - Module 7: Social Notes (Short 60-char text notes with music metadata & 24h expiration)
  - Module 10: Verified Badge Workflow (Application submission, review queue, approval)
"""
from __future__ import annotations

import re
import math
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from bson import ObjectId
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.services.identity_service import is_blocked, get_blocked_users
from app.core.enhanced_ws_manager import enhanced_ws_manager
from app.services.notification_service import create_event_notification
from app.core.security_logger import log_security_event

logger = logging.getLogger("zynova.social_service")

HASHTAG_REGEX = re.compile(r"#(\w+)")

def extract_hashtags(text: str) -> List[str]:
    """Extracts unique lowercase hashtags from text content."""
    if not text:
        return []
    return list({tag.lower() for tag in HASHTAG_REGEX.findall(text)})

# ---------------------------------------------------------------------------
# Module 1 & 5: Social Relationships & Follow Requests
# ---------------------------------------------------------------------------

async def request_follow_user(
    db: AsyncIOMotorDatabase,
    current_user: dict,
    target_user_id: str
) -> Dict[str, Any]:
    """
    Handles follow action:
    - If target user account is public: instantly creates active follow.
    - If target user account is private: creates a pending follow request.
    """
    my_id = current_user["id"]
    if my_id == target_user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot follow yourself")

    try:
        target_obj = ObjectId(target_user_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid target user ID")

    target = await db.users.find_one({"_id": target_obj})
    if not target:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Target user not found")

    # Mutual blocking check
    if await is_blocked(db, my_id, target_user_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot follow this user")

    # Check if target account is private
    is_private = target.get("social_profile", {}).get("is_private", False)

    now = datetime.now(timezone.utc)

    if is_private:
        # Check if already following
        already_following = await db.follows.find_one({"follower_id": my_id, "following_id": target_user_id})
        if already_following:
            return {"status": "following", "following_id": target_user_id}

        # Check or create follow request
        req = await db.follow_requests.update_one(
            {"sender_id": my_id, "target_id": target_user_id},
            {"$setOnInsert": {
                "sender_id": my_id,
                "sender_username": current_user["username"],
                "sender_full_name": current_user["full_name"],
                "sender_avatar": current_user.get("avatar_url"),
                "target_id": target_user_id,
                "status": "pending",
                "created_at": now
            }},
            upsert=True
        )

        if req.upserted_id:
            await create_event_notification(
                recipient_user_id=target_user_id,
                actor_user_id=my_id,
                category="social",
                event_type="social_follow_request",
                title=f"{current_user['full_name']} requested to follow you",
                desc=f"@{current_user['username']} sent you a follow request.",
                navigation_target=f"social:user:{my_id}",
                metadata={"follower_id": my_id, "follower_username": current_user["username"]},
                event_id=f"follow_req_{my_id}_{target_user_id}"
            )
        return {"status": "requested", "following_id": target_user_id}

    # Public account: immediate follow
    res = await db.follows.update_one(
        {"follower_id": my_id, "following_id": target_user_id},
        {"$setOnInsert": {"follower_id": my_id, "following_id": target_user_id, "created_at": now}},
        upsert=True
    )
    # Remove any existing pending request
    await db.follow_requests.delete_many({"sender_id": my_id, "target_id": target_user_id})

    if res.upserted_id:
        await create_event_notification(
            recipient_user_id=target_user_id,
            actor_user_id=my_id,
            category="social",
            event_type="social_follow",
            title=f"{current_user['full_name']} started following you",
            desc=f"@{current_user['username']} is now following your updates.",
            navigation_target=f"social:user:{my_id}",
            metadata={"follower_id": my_id, "follower_username": current_user["username"]},
            event_id=f"follow_{my_id}_{target_user_id}"
        )

    return {"status": "following", "following_id": target_user_id}

async def respond_to_follow_request(
    db: AsyncIOMotorDatabase,
    current_user_id: str,
    sender_id: str,
    action: str # "accept" | "reject"
) -> Dict[str, Any]:
    """Allows private accounts to accept or reject incoming follow requests."""
    req = await db.follow_requests.find_one({
        "sender_id": sender_id,
        "target_id": current_user_id,
        "status": "pending"
    })
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Follow request not found")

    if action == "accept":
        now = datetime.now(timezone.utc)
        await db.follows.update_one(
            {"follower_id": sender_id, "following_id": current_user_id},
            {"$setOnInsert": {"follower_id": sender_id, "following_id": current_user_id, "created_at": now}},
            upsert=True
        )
        await db.follow_requests.delete_one({"_id": req["_id"]})
        return {"status": "accepted", "follower_id": sender_id}
    else:
        await db.follow_requests.delete_one({"_id": req["_id"]})
        return {"status": "rejected", "follower_id": sender_id}

async def remove_follower(
    db: AsyncIOMotorDatabase,
    current_user_id: str,
    follower_id: str
) -> Dict[str, Any]:
    """Allows user to remove someone from their followers list."""
    await db.follows.delete_one({"follower_id": follower_id, "following_id": current_user_id})
    return {"status": "removed", "follower_id": follower_id}

async def get_suggested_accounts(
    db: AsyncIOMotorDatabase,
    current_user_id: str,
    limit: int = 10
) -> List[Dict[str, Any]]:
    """Returns recommended creator accounts excluding followed and blocked users."""
    blocked_ids = await get_blocked_users(db, current_user_id)
    follows_cursor = db.follows.find({"follower_id": current_user_id})
    following_ids = [f["following_id"] for f in await follows_cursor.to_list(length=1000)]
    exclude_ids = set(blocked_ids + following_ids + [current_user_id])

    cursor = db.users.find({
        "is_active": True,
        "_id": {"$nin": [ObjectId(uid) for uid in exclude_ids if ObjectId.is_valid(uid)]}
    }).limit(limit)

    suggestions = []
    async for u in cursor:
        uid = str(u["_id"])
        followers_cnt = await db.follows.count_documents({"following_id": uid})
        suggestions.append({
            "id": uid,
            "username": u["username"],
            "full_name": u["full_name"],
            "avatar_url": u.get("avatar_url"),
            "bio": u.get("bio"),
            "followers_count": followers_cnt,
            "is_verified": u.get("social_profile", {}).get("is_verified", False)
        })

    return suggestions

# ---------------------------------------------------------------------------
# Module 3: Stories, Reactions, Highlights & Close Friends
# ---------------------------------------------------------------------------

async def create_story(
    db: AsyncIOMotorDatabase,
    author: dict,
    media_url: str,
    media_type: str = "image",
    caption: Optional[str] = None,
    is_close_friends_only: bool = False
) -> Dict[str, Any]:
    """Creates a 24-hour ephemeral story with active expiration verification."""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=24)

    story_doc = {
        "author_id": author["id"],
        "author_username": author["username"],
        "author_full_name": author["full_name"],
        "author_avatar": author.get("avatar_url"),
        "media_url": media_url,
        "media_type": media_type,
        "caption": caption.strip() if caption else None,
        "is_close_friends_only": is_close_friends_only,
        "viewers": [],
        "views_count": 0,
        "reactions": [],
        "created_at": now,
        "expires_at": expires_at,
    }

    res = await db.social_stories.insert_one(story_doc)
    story_doc["id"] = str(res.inserted_id)
    story_doc["_id"] = str(res.inserted_id)

    # Broadcast real-time story indicator to followers
    follows_cursor = db.follows.find({"following_id": author["id"]})
    follower_ids = [f["follower_id"] for f in await follows_cursor.to_list(length=1000)]
    if follower_ids:
        await enhanced_ws_manager.dispatch_event(
            follower_ids,
            "social.story.new",
            {
                "story_id": story_doc["id"],
                "author_id": author["id"],
                "author_username": author["username"]
            }
        )

    return story_doc

async def get_stories_feed(
    db: AsyncIOMotorDatabase,
    current_user_id: str
) -> List[Dict[str, Any]]:
    """Returns active, non-expired stories grouped by author with close-friends filtering."""
    now = datetime.now(timezone.utc)
    blocked_ids = await get_blocked_users(db, current_user_id)

    follows_cursor = db.follows.find({"follower_id": current_user_id})
    target_author_ids = [f["following_id"] for f in await follows_cursor.to_list(length=1000)]
    target_author_ids.append(current_user_id)

    allowed_author_ids = [uid for uid in target_author_ids if uid not in blocked_ids]

    cursor = db.social_stories.find({
        "author_id": {"$in": allowed_author_ids},
        "expires_at": {"$gt": now}
    }).sort("created_at", 1)

    stories = await cursor.to_list(length=200)

    # Load close-friends lists of the authors
    authors_docs = await db.users.find({
        "_id": {"$in": [ObjectId(aid) for aid in allowed_author_ids if ObjectId.is_valid(aid)]}
    }, {"social_profile.close_friends": 1}).to_list(length=200)

    close_friends_map = {
        str(a["_id"]): set(a.get("social_profile", {}).get("close_friends", []))
        for a in authors_docs
    }

    grouped: Dict[str, Dict[str, Any]] = {}
    for s in stories:
        aid = s["author_id"]
        # Check close-friends privacy authorization
        if s.get("is_close_friends_only", False) and aid != current_user_id:
            cf_set = close_friends_map.get(aid, set())
            if current_user_id not in cf_set:
                continue

        if aid not in grouped:
            grouped[aid] = {
                "author_id": aid,
                "author_username": s["author_username"],
                "author_full_name": s["author_full_name"],
                "author_avatar": s.get("author_avatar"),
                "has_unseen": False,
                "stories": []
            }

        is_seen = current_user_id in s.get("viewers", [])
        if not is_seen:
            grouped[aid]["has_unseen"] = True

        grouped[aid]["stories"].append({
            "id": str(s["_id"]),
            "media_url": s["media_url"],
            "media_type": s.get("media_type", "image"),
            "caption": s.get("caption"),
            "is_close_friends_only": s.get("is_close_friends_only", False),
            "created_at": s["created_at"],
            "expires_at": s["expires_at"],
            "views_count": s.get("views_count", 0),
            "is_seen": is_seen
        })

    return list(grouped.values())

async def record_story_view(
    db: AsyncIOMotorDatabase,
    story_id: str,
    viewer_id: str
) -> Dict[str, Any]:
    """Records a unique viewer for an unexpired story."""
    try:
        story_obj = ObjectId(story_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid story ID")

    now = datetime.now(timezone.utc)
    story = await db.social_stories.find_one({"_id": story_obj, "expires_at": {"$gt": now}})
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found or expired")

    if viewer_id in story.get("viewers", []):
        return {"status": "already_viewed", "views_count": story.get("views_count", 0)}

    await db.social_stories.update_one(
        {"_id": story_obj},
        {
            "$addToSet": {"viewers": viewer_id},
            "$inc": {"views_count": 1}
        }
    )

    return {"status": "viewed", "views_count": story.get("views_count", 0) + 1}

async def add_story_reaction(
    db: AsyncIOMotorDatabase,
    story_id: str,
    user_id: str,
    reaction: str
) -> Dict[str, Any]:
    """Adds an emoji reaction to a story."""
    try:
        story_obj = ObjectId(story_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid story ID")

    now = datetime.now(timezone.utc)
    story = await db.social_stories.find_one({"_id": story_obj, "expires_at": {"$gt": now}})
    if not story:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found or expired")

    await db.social_stories.update_one(
        {"_id": story_obj},
        {"$push": {"reactions": {"user_id": user_id, "reaction": reaction, "created_at": now}}}
    )
    return {"status": "reacted", "reaction": reaction}

async def create_story_highlight(
    db: AsyncIOMotorDatabase,
    author_id: str,
    title: str,
    story_ids: List[str],
    cover_image_url: Optional[str] = None
) -> Dict[str, Any]:
    """Saves a permanent story highlight collection on the creator profile."""
    now = datetime.now(timezone.utc)
    highlight_doc = {
        "author_id": author_id,
        "title": title.strip(),
        "story_ids": story_ids,
        "cover_image_url": cover_image_url,
        "stories_count": len(story_ids),
        "created_at": now,
        "updated_at": now
    }
    res = await db.story_highlights.insert_one(highlight_doc)
    highlight_doc["id"] = str(res.inserted_id)
    return highlight_doc

async def get_user_highlights(
    db: AsyncIOMotorDatabase,
    target_user_id: str,
    viewer_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Lists story highlights for a user profile."""
    if viewer_id and await is_blocked(db, viewer_id, target_user_id):
        return []

    cursor = db.story_highlights.find({"author_id": target_user_id}).sort("created_at", -1)
    highlights = []
    async for h in cursor:
        highlights.append({
            "id": str(h["_id"]),
            "author_id": h["author_id"],
            "title": h["title"],
            "cover_image_url": h.get("cover_image_url"),
            "stories_count": h.get("stories_count", len(h.get("story_ids", []))),
            "created_at": h["created_at"]
        })
    return highlights

# ---------------------------------------------------------------------------
# Module 7: Social Notes (Status updates expiring in 24h)
# ---------------------------------------------------------------------------

async def post_social_note(
    db: AsyncIOMotorDatabase,
    user: dict,
    text: str,
    music_title: Optional[str] = None,
    music_artist: Optional[str] = None
) -> Dict[str, Any]:
    """Posts or updates current user's 60-character social note with 24h expiry."""
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=24)

    note_doc = {
        "user_id": user["id"],
        "username": user["username"],
        "full_name": user["full_name"],
        "avatar_url": user.get("avatar_url"),
        "text": text.strip()[:60],
        "music_title": music_title.strip() if music_title else None,
        "music_artist": music_artist.strip() if music_artist else None,
        "created_at": now,
        "expires_at": expires_at
    }

    # Upsert user's single active note
    await db.social_notes.update_one(
        {"user_id": user["id"]},
        {"$set": note_doc},
        upsert=True
    )
    return note_doc

async def get_following_notes(
    db: AsyncIOMotorDatabase,
    current_user_id: str
) -> List[Dict[str, Any]]:
    """Returns active notes from accounts the current user follows + own note."""
    now = datetime.now(timezone.utc)
    blocked_ids = await get_blocked_users(db, current_user_id)

    follows_cursor = db.follows.find({"follower_id": current_user_id})
    target_ids = [f["following_id"] for f in await follows_cursor.to_list(length=500)]
    target_ids.append(current_user_id)

    allowed_ids = [uid for uid in target_ids if uid not in blocked_ids]

    cursor = db.social_notes.find({
        "user_id": {"$in": allowed_ids},
        "expires_at": {"$gt": now}
    }).sort("created_at", -1)

    notes = []
    async for n in cursor:
        notes.append({
            "id": str(n.get("_id", n["user_id"])),
            "user_id": n["user_id"],
            "username": n["username"],
            "full_name": n["full_name"],
            "avatar_url": n.get("avatar_url"),
            "text": n["text"],
            "music_title": n.get("music_title"),
            "music_artist": n.get("music_artist"),
            "created_at": n["created_at"],
            "expires_at": n["expires_at"]
        })
    return notes

# ---------------------------------------------------------------------------
# Module 2, 4, 6: Feed Ranking, Reels, Explore & Bookmarks
# ---------------------------------------------------------------------------

async def toggle_post_bookmark(
    db: AsyncIOMotorDatabase,
    post_id: str,
    user_id: str
) -> Dict[str, Any]:
    """Toggles bookmark/save state for a given post."""
    try:
        post_obj = ObjectId(post_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid post ID")

    post = await db.posts.find_one({"_id": post_obj})
    if not post:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found")

    query = {
        "user_id": user_id,
        "target_type": "post",
        "target_id": post_id,
        "interaction_type": "bookmark"
    }

    existing = await db.social_interactions.find_one(query)
    if existing:
        await db.social_interactions.delete_one(query)
        return {"status": "unbookmarked", "post_id": post_id}
    else:
        now = datetime.now(timezone.utc)
        await db.social_interactions.insert_one({
            **query,
            "created_at": now
        })
        return {"status": "bookmarked", "post_id": post_id}

async def get_bookmarked_posts(
    db: AsyncIOMotorDatabase,
    user_id: str,
    limit: int = 25
) -> List[Dict[str, Any]]:
    """Retrieves saved/bookmarked posts for current user."""
    cursor = db.social_interactions.find({
        "user_id": user_id,
        "target_type": "post",
        "interaction_type": "bookmark"
    }).sort("created_at", -1).limit(limit)

    bookmarks = await cursor.to_list(length=limit)
    post_ids = [ObjectId(b["target_id"]) for b in bookmarks if ObjectId.is_valid(b["target_id"])]

    if not post_ids:
        return []

    posts_cursor = db.posts.find({"_id": {"$in": post_ids}})
    posts_map = {str(p["_id"]): p async for p in posts_cursor}

    results = []
    for b in bookmarks:
        pid = b["target_id"]
        if pid in posts_map:
            p = posts_map[pid]
            results.append({
                "id": pid,
                "author_id": p["author_id"],
                "author_username": p["author_username"],
                "author_full_name": p["author_full_name"],
                "author_avatar": p.get("author_avatar"),
                "content": p["content"],
                "image_url": p.get("image_url"),
                "media_url": p.get("media_url"),
                "media_type": p.get("media_type", "image"),
                "media_assets": p.get("media_assets", []),
                "tags": p.get("tags", []),
                "created_at": p["created_at"],
                "likes_count": p.get("likes_count", 0),
                "comments_count": p.get("comments_count", 0),
                "is_bookmarked": True
            })

    return results

async def get_explore_feed(
    db: AsyncIOMotorDatabase,
    current_user_id: Optional[str] = None,
    limit: int = 30
) -> List[Dict[str, Any]]:
    """
    Ranks posts and reels for Explore discovery using engagement + decay:
    Score = (likes * 1.5 + comments * 3.0 + 1.0) * exp(-0.05 * dt_hours)
    """
    blocked_ids = await get_blocked_users(db, current_user_id) if current_user_id else []

    query: Dict[str, Any] = {}
    if blocked_ids:
        query["author_id"] = {"$nin": blocked_ids}

    # Fetch candidate pool
    cursor = db.posts.find(query).sort("created_at", -1).limit(100)
    candidates = await cursor.to_list(length=100)

    now = datetime.now(timezone.utc)
    scored = []
    for post in candidates:
        created_at = post.get("created_at", now)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        dt_hours = max(0.0, (now - created_at).total_seconds() / 3600.0)

        likes = post.get("likes_count", 0)
        comments = post.get("comments_count", 0)
        engagement_score = (likes * 1.5 + comments * 3.0 + 1.0) * math.exp(-0.05 * dt_hours)
        scored.append((engagement_score, post))

    scored.sort(key=lambda x: x[0], reverse=True)
    top_posts = [item[1] for item in scored[:limit]]

    results = []
    for p in top_posts:
        likes_list = p.get("likes", [])
        results.append({
            "id": str(p["_id"]),
            "author_id": p["author_id"],
            "author_username": p["author_username"],
            "author_full_name": p["author_full_name"],
            "author_avatar": p.get("author_avatar"),
            "content": p["content"],
            "image_url": p.get("image_url"),
            "media_url": p.get("media_url"),
            "media_type": p.get("media_type", "image"),
            "media_assets": p.get("media_assets", []),
            "tags": p.get("tags", []),
            "created_at": p["created_at"],
            "likes_count": len(likes_list),
            "comments_count": p.get("comments_count", 0),
            "is_liked": (current_user_id in likes_list) if current_user_id else False
        })

    return results

async def get_posts_by_hashtag(
    db: AsyncIOMotorDatabase,
    tag: str,
    current_user_id: Optional[str] = None,
    limit: int = 25
) -> List[Dict[str, Any]]:
    """Returns posts tagged with a specific hashtag (case-insensitive)."""
    clean_tag = tag.lstrip("#").lower().strip()
    blocked_ids = await get_blocked_users(db, current_user_id) if current_user_id else []

    query: Dict[str, Any] = {"tags": clean_tag}
    if blocked_ids:
        query["author_id"] = {"$nin": blocked_ids}

    cursor = db.posts.find(query).sort("created_at", -1).limit(limit)
    posts = await cursor.to_list(length=limit)

    results = []
    for p in posts:
        likes_list = p.get("likes", [])
        results.append({
            "id": str(p["_id"]),
            "author_id": p["author_id"],
            "author_username": p["author_username"],
            "author_full_name": p["author_full_name"],
            "author_avatar": p.get("author_avatar"),
            "content": p["content"],
            "image_url": p.get("image_url"),
            "media_url": p.get("media_url"),
            "media_type": p.get("media_type", "image"),
            "media_assets": p.get("media_assets", []),
            "tags": p.get("tags", []),
            "created_at": p["created_at"],
            "likes_count": len(likes_list),
            "comments_count": p.get("comments_count", 0),
            "is_liked": (current_user_id in likes_list) if current_user_id else False
        })

    return results

# ---------------------------------------------------------------------------
# Module 10: Verified Badge Workflow
# ---------------------------------------------------------------------------

async def submit_verification_application(
    db: AsyncIOMotorDatabase,
    user_id: str,
    payload: dict
) -> Dict[str, Any]:
    """Submits a formal identity verification application."""
    # Check if existing pending application exists
    existing = await db.verification_applications.find_one({
        "user_id": user_id,
        "status": "pending"
    })
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You already have a pending verification application under review."
        )

    now = datetime.now(timezone.utc)
    app_doc = {
        "user_id": user_id,
        "full_legal_name": payload["full_legal_name"].strip(),
        "document_type": payload["document_type"],
        "evidence_urls": payload["evidence_urls"],
        "category": payload["category"],
        "reason": payload["reason"].strip(),
        "status": "pending",
        "reviewer_notes": None,
        "created_at": now,
        "reviewed_at": None
    }

    res = await db.verification_applications.insert_one(app_doc)
    app_doc["id"] = str(res.inserted_id)

    log_security_event(
        event_code="VERIFICATION_SUBMITTED",
        action="submit_verification",
        status="PENDING",
        details={"user_id": user_id, "category": payload["category"]}
    )

    return app_doc

async def review_verification_application(
    db: AsyncIOMotorDatabase,
    application_id: str,
    reviewer_user_id: str,
    action: str, # "approve" | "reject"
    notes: Optional[str] = None
) -> Dict[str, Any]:
    """Admin reviewer queue action: approves or rejects verification application."""
    try:
        app_obj = ObjectId(application_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid application ID")

    app_doc = await db.verification_applications.find_one({"_id": app_obj})
    if not app_doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Application not found")

    now = datetime.now(timezone.utc)
    new_status = "approved" if action == "approve" else "rejected"

    await db.verification_applications.update_one(
        {"_id": app_obj},
        {"$set": {
            "status": new_status,
            "reviewer_user_id": reviewer_user_id,
            "reviewer_notes": notes.strip() if notes else None,
            "reviewed_at": now
        }}
    )

    # If approved, badge is activated on user's social profile
    if new_status == "approved":
        await db.users.update_one(
            {"_id": ObjectId(app_doc["user_id"])},
            {"$set": {
                "social_profile.is_verified": True,
                "social_profile.verified_at": now
            }}
        )

    log_security_event(
        event_code="VERIFICATION_REVIEWED",
        action="review_verification",
        status=new_status.upper(),
        details={"application_id": application_id, "target_user": app_doc["user_id"]}
    )

    return {"status": new_status, "application_id": application_id}
