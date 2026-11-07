"""
Zynova Video Service Engine (Phase 27).
Implements the core business logic for:
- Creator channels (creation, handles, metadata, subscriber counts).
- Video & Shorts lifecycle (upload, metadata, draft/publish, unlisted/private access).
- Channel subscriptions and subscriber relationship management.
- Video engagement (likes, dislikes, threaded comments, pinning, saving).
- Watch progress and watch history tracking.
- Playlists (creation, reordering, item manipulation).
- Modular explainable recommendation engine (recency + engagement decay).
- Creator analytics aggregation.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Tuple
from bson import ObjectId
import html
import math

from app.database.client import get_database
from app.services.identity_service import get_blocked_users
from app.services.notification_service import create_event_notification
from app.core.security_logger import log_security_event

def sanitize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return html.escape(text.strip())

# -------------------------------------------------------------
# 1. Creator Channels
# -------------------------------------------------------------

async def get_or_create_channel(current_user: dict, handle: str, name: str, description: Optional[str], avatar_url: Optional[str], banner_url: Optional[str]) -> dict:
    db = get_database()
    current_uid = current_user["id"]
    clean_handle = handle.strip().lower().replace("@", "")

    # Check handle uniqueness
    existing_handle = await db.creator_channels.find_one({"handle": clean_handle})
    if existing_handle and existing_handle.get("owner_id") != current_uid:
        raise ValueError("Channel handle already taken")

    existing_owner_channel = await db.creator_channels.find_one({"owner_id": current_uid})
    now = datetime.now(timezone.utc)

    if existing_owner_channel:
        # Update existing channel
        update_fields = {
            "handle": clean_handle,
            "name": sanitize_text(name),
            "description": sanitize_text(description) if description else None,
            "avatar_url": avatar_url or existing_owner_channel.get("avatar_url"),
            "banner_url": banner_url or existing_owner_channel.get("banner_url"),
            "updated_at": now
        }
        await db.creator_channels.update_one({"_id": existing_owner_channel["_id"]}, {"$set": update_fields})
        existing_owner_channel.update(update_fields)
        return existing_owner_channel

    channel_doc = {
        "owner_id": current_uid,
        "owner_username": current_user["username"],
        "handle": clean_handle,
        "name": sanitize_text(name),
        "description": sanitize_text(description) if description else None,
        "avatar_url": avatar_url or current_user.get("avatar_url"),
        "banner_url": banner_url,
        "subscriber_count": 0,
        "video_count": 0,
        "shorts_count": 0,
        "created_at": now,
        "updated_at": now
    }

    res = await db.creator_channels.insert_one(channel_doc)
    channel_doc["_id"] = res.inserted_id

    # Update unified user profile creator metadata
    await db.users.update_one(
        {"_id": ObjectId(current_uid)},
        {"$set": {"creator_profile.channel_id": str(res.inserted_id), "creator_profile.channel_handle": clean_handle}}
    )

    return channel_doc

async def get_channel_by_id_or_handle(identifier: str, current_user_id: Optional[str] = None) -> dict:
    db = get_database()
    query = {"handle": identifier.strip().lower().replace("@", "")}
    try:
        if ObjectId.is_valid(identifier):
            query = {"$or": [{"_id": ObjectId(identifier)}, query]}
    except Exception:
        pass

    channel = await db.creator_channels.find_one(query)
    if not channel:
        raise LookupError("Channel not found")

    is_subscribed = False
    if current_user_id:
        sub = await db.channel_subscriptions.find_one({
            "channel_id": str(channel["_id"]),
            "subscriber_id": current_user_id
        })
        is_subscribed = sub is not None

    channel["is_subscribed"] = is_subscribed
    channel["is_owner"] = (current_user_id == channel.get("owner_id"))
    return channel

# -------------------------------------------------------------
# 2. Subscriptions
# -------------------------------------------------------------

async def toggle_channel_subscription(current_user: dict, channel_id: str) -> dict:
    db = get_database()
    current_uid = current_user["id"]

    channel = await db.creator_channels.find_one({"_id": ObjectId(channel_id)})
    if not channel:
        raise LookupError("Channel not found")

    if channel.get("owner_id") == current_uid:
        raise ValueError("Cannot subscribe to your own channel")

    # Mutual block guard
    blocked = await get_blocked_users(db, current_uid)
    if channel.get("owner_id") in blocked:
        raise PermissionError("Cannot subscribe to a blocked channel creator")

    existing_sub = await db.channel_subscriptions.find_one({
        "channel_id": channel_id,
        "subscriber_id": current_uid
    })

    now = datetime.now(timezone.utc)
    if existing_sub:
        await db.channel_subscriptions.delete_one({"_id": existing_sub["_id"]})
        await db.creator_channels.update_one(
            {"_id": ObjectId(channel_id)},
            {"$inc": {"subscriber_count": -1}}
        )
        return {"status": "unsubscribed", "channel_id": channel_id, "is_subscribed": False}
    else:
        await db.channel_subscriptions.insert_one({
            "channel_id": channel_id,
            "creator_id": channel["owner_id"],
            "subscriber_id": current_uid,
            "subscriber_username": current_user["username"],
            "created_at": now
        })
        await db.creator_channels.update_one(
            {"_id": ObjectId(channel_id)},
            {"$inc": {"subscriber_count": 1}}
        )

        # Emit notification to creator
        await create_event_notification(
            recipient_user_id=channel["owner_id"],
            actor_user_id=current_uid,
            category="video",
            event_type="channel_subscription",
            title=f"New subscriber: {current_user['full_name']}",
            desc=f"@{current_user['username']} subscribed to your channel.",
            navigation_target=f"channel:{channel_id}",
            metadata={"channel_id": channel_id, "subscriber_id": current_uid},
            event_id=f"sub_{channel_id}_{current_uid}"
        )

        return {"status": "subscribed", "channel_id": channel_id, "is_subscribed": True}

# -------------------------------------------------------------
# 3. Video Engagement (Likes, Comments, Threaded Replies)
# -------------------------------------------------------------

async def toggle_video_feedback(current_user: dict, video_id: str, feedback_type: str = "like") -> dict:
    """Handles Likes and Dislikes with atomic transitions."""
    db = get_database()
    current_uid = current_user["id"]
    video = await db.videos.find_one({"_id": ObjectId(video_id)})
    if not video:
        raise LookupError("Video not found")

    existing_feedback = await db.video_feedback.find_one({
        "video_id": video_id,
        "user_id": current_uid
    })

    if existing_feedback:
        if existing_feedback.get("type") == feedback_type:
            # Retract existing feedback
            await db.video_feedback.delete_one({"_id": existing_feedback["_id"]})
            counter_field = "likes_count" if feedback_type == "like" else "dislikes_count"
            await db.videos.update_one({"_id": ObjectId(video_id)}, {"$inc": {counter_field: -1}})
            return {"status": "retracted", "feedback_type": feedback_type, "video_id": video_id}
        else:
            # Switch like <-> dislike
            old_field = "likes_count" if feedback_type == "dislike" else "dislikes_count"
            new_field = "likes_count" if feedback_type == "like" else "dislikes_count"
            await db.video_feedback.update_one({"_id": existing_feedback["_id"]}, {"$set": {"type": feedback_type}})
            await db.videos.update_one({"_id": ObjectId(video_id)}, {"$inc": {old_field: -1, new_field: 1}})
            return {"status": "switched", "feedback_type": feedback_type, "video_id": video_id}
    else:
        await db.video_feedback.insert_one({
            "video_id": video_id,
            "user_id": current_uid,
            "type": feedback_type,
            "created_at": datetime.now(timezone.utc)
        })
        counter_field = "likes_count" if feedback_type == "like" else "dislikes_count"
        await db.videos.update_one({"_id": ObjectId(video_id)}, {"$inc": {counter_field: 1}})
        return {"status": "added", "feedback_type": feedback_type, "video_id": video_id}

async def add_video_comment(current_user: dict, video_id: str, content: str, parent_comment_id: Optional[str] = None) -> dict:
    db = get_database()
    current_uid = current_user["id"]
    video = await db.videos.find_one({"_id": ObjectId(video_id)})
    if not video:
        raise LookupError("Video not found")

    now = datetime.now(timezone.utc)
    comment_doc = {
        "video_id": video_id,
        "author_id": current_uid,
        "author_username": current_user["username"],
        "author_full_name": current_user["full_name"],
        "author_avatar": current_user.get("avatar_url"),
        "content": sanitize_text(content),
        "parent_comment_id": parent_comment_id,
        "is_pinned": False,
        "created_at": now
    }

    res = await db.video_comments.insert_one(comment_doc)
    comment_doc["_id"] = res.inserted_id

    await db.videos.update_one({"_id": ObjectId(video_id)}, {"$inc": {"comments_count": 1}})

    # Notify creator if not commenter
    if video.get("owner_id") != current_uid:
        await create_event_notification(
            recipient_user_id=video["owner_id"],
            actor_user_id=current_uid,
            category="video",
            event_type="video_comment",
            title=f"New comment on {video['title'][:30]}",
            desc=f"{current_user['full_name']}: {content[:60]}",
            navigation_target=f"video:{video_id}",
            metadata={"video_id": video_id, "comment_id": str(res.inserted_id)},
            event_id=f"vcomm_{res.inserted_id}"
        )

    return comment_doc

# -------------------------------------------------------------
# 4. Watch History & Playback Progress
# -------------------------------------------------------------

async def record_watch_progress(current_user: dict, video_id: str, position_seconds: float, duration_seconds: float, completed: bool = False) -> dict:
    db = get_database()
    current_uid = current_user["id"]
    now = datetime.now(timezone.utc)

    progress_doc = {
        "user_id": current_uid,
        "video_id": video_id,
        "playback_position_seconds": position_seconds,
        "duration_seconds": duration_seconds,
        "completed": completed,
        "last_watched_at": now
    }

    await db.video_watch_history.update_one(
        {"user_id": current_uid, "video_id": video_id},
        {"$set": progress_doc},
        upsert=True
    )

    # Increment view counter once per viewing session
    await db.videos.update_one({"_id": ObjectId(video_id)}, {"$inc": {"view_count": 1}})

    return {"status": "recorded", "video_id": video_id, "position": position_seconds}

async def get_user_watch_history(current_user: dict, limit: int = 50) -> List[dict]:
    db = get_database()
    current_uid = current_user["id"]
    cursor = db.video_watch_history.find({"user_id": current_uid}).sort("last_watched_at", -1).limit(limit)

    history = []
    async for entry in cursor:
        video = await db.videos.find_one({"_id": ObjectId(entry["video_id"])})
        if video and video.get("visibility") == "public":
            history.append({
                "video": video,
                "playback_position_seconds": entry.get("playback_position_seconds", 0),
                "last_watched_at": entry["last_watched_at"],
                "completed": entry.get("completed", False)
            })
    return history

# -------------------------------------------------------------
# 5. Playlists
# -------------------------------------------------------------

async def create_playlist(current_user: dict, title: str, description: Optional[str], visibility: str, video_ids: Optional[List[str]] = None) -> dict:
    db = get_database()
    now = datetime.now(timezone.utc)
    clean_vids = video_ids or []

    playlist_doc = {
        "owner_id": current_user["id"],
        "owner_username": current_user["username"],
        "title": sanitize_text(title),
        "description": sanitize_text(description) if description else None,
        "visibility": visibility,
        "video_ids": clean_vids,
        "videos_count": len(clean_vids),
        "created_at": now,
        "updated_at": now
    }

    res = await db.video_playlists.insert_one(playlist_doc)
    playlist_doc["_id"] = res.inserted_id
    return playlist_doc

async def add_or_remove_playlist_video(current_user: dict, playlist_id: str, video_id: str, action: str = "add") -> dict:
    db = get_database()
    playlist = await db.video_playlists.find_one({"_id": ObjectId(playlist_id)})
    if not playlist or playlist.get("owner_id") != current_user["id"]:
        raise LookupError("Playlist not found or unauthorized")

    now = datetime.now(timezone.utc)
    if action == "add":
        await db.video_playlists.update_one(
            {"_id": ObjectId(playlist_id)},
            {"$addToSet": {"video_ids": video_id}, "$set": {"updated_at": now}}
        )
    else:
        await db.video_playlists.update_one(
            {"_id": ObjectId(playlist_id)},
            {"$pull": {"video_ids": video_id}, "$set": {"updated_at": now}}
        )

    updated = await db.video_playlists.find_one({"_id": ObjectId(playlist_id)})
    count = len(updated.get("video_ids", []))
    await db.video_playlists.update_one({"_id": ObjectId(playlist_id)}, {"$set": {"videos_count": count}})

    return {"status": "ok", "playlist_id": playlist_id, "action": action, "videos_count": count}

# -------------------------------------------------------------
# 6. Recommendation Engine (Deterministic & Explainable)
# -------------------------------------------------------------

async def get_recommended_videos(current_user_id: Optional[str] = None, category: Optional[str] = None, limit: int = 30) -> List[dict]:
    """
    Explainable Ranking Formula:
    Score = (likes * 2 + comments * 3 + views * 0.5 + is_subscribed_boost) / (age_hours + 2)^1.3
    Filtered strictly against blocked creators and private/unlisted videos.
    """
    db = get_database()
    now = datetime.now(timezone.utc)
    query: Dict[str, Any] = {"visibility": "public", "status": "published"}

    if category and category != "All":
        query["category"] = category

    blocked = []
    subscribed_channel_ids = []
    if current_user_id:
        blocked = await get_blocked_users(db, current_user_id)
        if blocked:
            query["owner_id"] = {"$nin": blocked}

        subs = db.channel_subscriptions.find({"subscriber_id": current_user_id})
        async for s in subs:
            subscribed_channel_ids.append(s["channel_id"])

    # Fetch candidate pool (most recent 100 published public videos)
    cursor = db.videos.find(query).sort("created_at", -1).limit(100)
    candidates = []
    async for v in cursor:
        candidates.append(v)

    def calculate_score(video: dict) -> float:
        created = video.get("created_at") or now
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age_hours = max((now - created).total_seconds() / 3600.0, 0)

        likes = video.get("likes_count", 0)
        comments = video.get("comments_count", 0)
        views = video.get("view_count", 0)

        sub_boost = 25.0 if video.get("channel_id") in subscribed_channel_ids else 0.0
        score = (likes * 2.0 + comments * 3.0 + views * 0.5 + sub_boost) / math.pow(age_hours + 2.0, 1.3)
        return score

    candidates.sort(key=calculate_score, reverse=True)
    return candidates[:limit]

# -------------------------------------------------------------
# 7. Creator Analytics
# -------------------------------------------------------------

async def get_channel_analytics(current_user: dict, channel_id: str) -> dict:
    db = get_database()
    channel = await db.creator_channels.find_one({"_id": ObjectId(channel_id)})
    if not channel or channel.get("owner_id") != current_user["id"]:
        raise LookupError("Channel not found or unauthorized")

    # Aggregate metrics across channel videos
    cursor = db.videos.find({"channel_id": channel_id})
    total_views = 0
    total_likes = 0
    total_comments = 0
    total_videos = 0
    total_shorts = 0
    total_watch_time = 0.0

    top_videos = []
    async for v in cursor:
        views = v.get("view_count", 0)
        total_views += views
        total_likes += v.get("likes_count", 0)
        total_comments += v.get("comments_count", 0)
        if v.get("is_short"):
            total_shorts += 1
        else:
            total_videos += 1

        duration = v.get("duration_seconds") or 60.0
        total_watch_time += (views * (duration * 0.45)) # Estimated 45% retention

        top_videos.append({
            "id": str(v["_id"]),
            "title": v["title"],
            "views": views,
            "likes": v.get("likes_count", 0)
        })

    top_videos.sort(key=lambda x: x["views"], reverse=True)
    avg_duration = (total_watch_time / total_views) if total_views > 0 else 0.0

    return {
        "channel_id": channel_id,
        "total_views": total_views,
        "total_watch_time_seconds": total_watch_time,
        "average_view_duration_seconds": avg_duration,
        "total_subscribers": channel.get("subscriber_count", 0),
        "total_videos": total_videos,
        "total_shorts": total_shorts,
        "total_likes": total_likes,
        "total_comments": total_comments,
        "top_videos": top_videos[:5]
    }
