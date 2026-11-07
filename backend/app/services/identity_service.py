"""
Unified Identity Service — Phase 24.1
Extends the existing `users` collection with platform-specific profile metadata
for Social, Connect, and Video without duplicating accounts or breaking auth.

Design constraints:
  - Single users collection; no duplicate identity records.
  - All platform sub-profiles are embedded as optional top-level fields.
  - Existing authentication (Argon2id + JWT) is 100% preserved.
  - Lazy initialisation: profiles are populated on first access, not at registration.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from bson import ObjectId
from fastapi import HTTPException, status
from motor.motor_asyncio import AsyncIOMotorDatabase

from app.core.security_logger import log_security_event

logger = logging.getLogger("zynova.identity")

# ---------------------------------------------------------------------------
# Default embedded sub-profile templates
# ---------------------------------------------------------------------------

def _default_social_profile() -> Dict[str, Any]:
    return {
        "is_private": False,
        "website": None,
        "pronouns": None,
        "allow_story_replies": "everyone",   # everyone | following | off
        "allow_mentions": "everyone",         # everyone | following | off
        "show_activity_status": True,
        "show_suggested_to_others": True,
    }


def _default_connect_profile() -> Dict[str, Any]:
    return {
        "display_name": None,          # Overrides full_name in Connect if set
        "about_text": "Hey there! I am using Zynova.",
        "last_seen_privacy": "everyone",   # everyone | contacts | nobody
        "read_receipts_enabled": True,
        "typing_indicators_enabled": True,
        "online_status_visible": True,
    }


def _default_video_channel() -> Dict[str, Any]:
    return {
        "handle": None,                # @handle (unique, set on first use)
        "channel_name": None,          # Display name for channel
        "channel_description": None,
        "banner_url": None,
        "subscribers_count": 0,
        "total_views": 0,
        "notification_preference": "personalized",  # all | personalized | none
        "created_at": datetime.now(timezone.utc),
    }


def _default_privacy_settings() -> Dict[str, Any]:
    return {
        "profile_visibility": "public",    # public | contacts | private
        "search_discoverable": True,
        "data_personalisation": True,
    }

# ---------------------------------------------------------------------------
# Profile retrieval & lazy initialisation
# ---------------------------------------------------------------------------

async def get_or_init_unified_profile(
    db: AsyncIOMotorDatabase,
    user_id: str,
) -> Dict[str, Any]:
    """
    Returns the full user document ensuring all platform sub-profiles exist.
    Missing sub-profiles are initialised lazily with safe defaults using $setOnInsert
    semantics (we use $set only for missing keys to avoid overwriting user data).
    """
    try:
        obj_id = ObjectId(user_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid user ID")

    user = await db.users.find_one({"_id": obj_id})
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    updates: Dict[str, Any] = {}

    if "social_profile" not in user:
        updates["social_profile"] = _default_social_profile()
    if "connect_profile" not in user:
        updates["connect_profile"] = _default_connect_profile()
    if "video_channel" not in user:
        updates["video_channel"] = _default_video_channel()
    if "privacy_settings" not in user:
        updates["privacy_settings"] = _default_privacy_settings()
    if "blocked_users" not in user:
        updates["blocked_users"] = []
    if "device_sessions" not in user:
        updates["device_sessions"] = []
    if "account_status" not in user:
        updates["account_status"] = "active"   # active | suspended | restricted

    if updates:
        await db.users.update_one({"_id": obj_id}, {"$set": updates})
        user.update(updates)

    user["id"] = str(user["_id"])
    return user


# ---------------------------------------------------------------------------
# Social profile updates
# ---------------------------------------------------------------------------

async def update_social_profile(
    db: AsyncIOMotorDatabase,
    user_id: str,
    updates: Dict[str, Any],
) -> Dict[str, Any]:
    """Updates only allowed social profile fields. Returns updated doc."""
    allowed_fields = {
        "is_private", "website", "pronouns",
        "allow_story_replies", "allow_mentions",
        "show_activity_status", "show_suggested_to_others",
    }
    safe = {k: v for k, v in updates.items() if k in allowed_fields}
    if not safe:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid social profile fields provided")

    set_ops = {f"social_profile.{k}": v for k, v in safe.items()}
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": set_ops})
    return await get_or_init_unified_profile(db, user_id)


# ---------------------------------------------------------------------------
# Connect profile updates
# ---------------------------------------------------------------------------

async def update_connect_profile(
    db: AsyncIOMotorDatabase,
    user_id: str,
    updates: Dict[str, Any],
) -> Dict[str, Any]:
    allowed_fields = {
        "display_name", "about_text",
        "last_seen_privacy", "read_receipts_enabled",
        "typing_indicators_enabled", "online_status_visible",
    }
    safe = {k: v for k, v in updates.items() if k in allowed_fields}
    if not safe:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="No valid connect profile fields provided")

    set_ops = {f"connect_profile.{k}": v for k, v in safe.items()}
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": set_ops})
    return await get_or_init_unified_profile(db, user_id)


# ---------------------------------------------------------------------------
# Video channel setup
# ---------------------------------------------------------------------------

async def setup_video_channel(
    db: AsyncIOMotorDatabase,
    user_id: str,
    handle: str,
    channel_name: str,
    description: Optional[str] = None,
) -> Dict[str, Any]:
    """Claims a unique @handle for the user's Video channel."""
    handle_clean = handle.lstrip("@").lower().strip()
    if not handle_clean or len(handle_clean) < 3:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Handle must be at least 3 characters")

    # Check handle uniqueness across all users
    existing = await db.users.find_one({"video_channel.handle": handle_clean})
    if existing and str(existing["_id"]) != user_id:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Channel handle already taken")

    updates = {
        "video_channel.handle": handle_clean,
        "video_channel.channel_name": channel_name.strip(),
        "video_channel.channel_description": description.strip() if description else None,
    }
    await db.users.update_one({"_id": ObjectId(user_id)}, {"$set": updates})
    return await get_or_init_unified_profile(db, user_id)


# ---------------------------------------------------------------------------
# Blocking relationships
# ---------------------------------------------------------------------------

async def block_user(
    db: AsyncIOMotorDatabase,
    actor_id: str,
    target_id: str,
) -> None:
    """Blocks target_id from actor's perspective. Also removes any follow relationship."""
    if actor_id == target_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot block yourself")

    await db.users.update_one(
        {"_id": ObjectId(actor_id)},
        {"$addToSet": {"blocked_users": target_id}}
    )
    # Clean up bidirectional follow relationships
    await db.follows.delete_many({
        "$or": [
            {"follower_id": actor_id, "following_id": target_id},
            {"follower_id": target_id, "following_id": actor_id},
        ]
    })
    log_security_event(
        event_code="USER_BLOCKED",
        action="block_user",
        status="SUCCESS",
        details={"actor": actor_id, "target": target_id}
    )


async def unblock_user(
    db: AsyncIOMotorDatabase,
    actor_id: str,
    target_id: str,
) -> None:
    await db.users.update_one(
        {"_id": ObjectId(actor_id)},
        {"$pull": {"blocked_users": target_id}}
    )


async def get_blocked_users(
    db: AsyncIOMotorDatabase,
    user_id: str,
) -> List[str]:
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"blocked_users": 1})
    return user.get("blocked_users", []) if user else []


async def is_blocked(
    db: AsyncIOMotorDatabase,
    viewer_id: str,
    subject_id: str,
) -> bool:
    """Returns True if viewer has blocked subject OR subject has blocked viewer."""
    viewer = await db.users.find_one({"_id": ObjectId(viewer_id)}, {"blocked_users": 1})
    subject = await db.users.find_one({"_id": ObjectId(subject_id)}, {"blocked_users": 1})
    viewer_blocks = set(viewer.get("blocked_users", [])) if viewer else set()
    subject_blocks = set(subject.get("blocked_users", [])) if subject else set()
    return subject_id in viewer_blocks or viewer_id in subject_blocks


# ---------------------------------------------------------------------------
# Device session management
# ---------------------------------------------------------------------------

async def register_device_session(
    db: AsyncIOMotorDatabase,
    user_id: str,
    session: Dict[str, Any],
) -> None:
    """
    Adds a device session entry to the user record.
    session keys: device_id, platform, device_name, push_token, registered_at
    """
    session.setdefault("registered_at", datetime.now(timezone.utc))
    session.setdefault("last_seen_at", datetime.now(timezone.utc))
    # Remove old entry for same device_id before inserting
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$pull": {"device_sessions": {"device_id": session.get("device_id")}}}
    )
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$addToSet": {"device_sessions": session}}
    )


async def revoke_device_session(
    db: AsyncIOMotorDatabase,
    user_id: str,
    device_id: str,
) -> None:
    await db.users.update_one(
        {"_id": ObjectId(user_id)},
        {"$pull": {"device_sessions": {"device_id": device_id}}}
    )
    log_security_event(
        event_code="DEVICE_SESSION_REVOKED",
        action="revoke_device",
        status="SUCCESS",
        details={"user": user_id, "device": device_id}
    )


async def get_device_sessions(
    db: AsyncIOMotorDatabase,
    user_id: str,
) -> List[Dict[str, Any]]:
    user = await db.users.find_one({"_id": ObjectId(user_id)}, {"device_sessions": 1})
    return user.get("device_sessions", []) if user else []
