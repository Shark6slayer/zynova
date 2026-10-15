import logging
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from app.database.client import get_database

logger = logging.getLogger("notifications")

async def create_event_notification(
    recipient_user_id: str,
    actor_user_id: Optional[str],
    category: str,
    event_type: str,
    title: str,
    desc: str,
    navigation_target: str,
    metadata: Optional[Dict[str, Any]] = None,
    event_id: Optional[str] = None
) -> Optional[str]:
    """
    Creates a persistent, server-side validated notification for a user.
    - Prevents notifying users of their own actions when actor_user_id == recipient_user_id.
    - Prevents duplicate event notifications via unique event_id idempotency.
    - Captures safe structured metadata linking to the relevant target resource.
    """
    # 1. Do not notify a user about their own action
    if actor_user_id and str(recipient_user_id) == str(actor_user_id):
        return None

    db = get_database()
    if db is None:
        logger.warning("Database unavailable, cannot record notification")
        return None

    now = datetime.now(timezone.utc)
    safe_metadata = metadata.copy() if metadata else {}
    safe_metadata["navigation_target"] = navigation_target

    doc = {
        "user_id": str(recipient_user_id),
        "actor_user_id": str(actor_user_id) if actor_user_id else None,
        "category": category,
        "event_type": event_type,
        "title": title.strip(),
        "desc": desc.strip(),
        "time": "Just now",
        "read": False,
        "read_at": None,
        "metadata": safe_metadata,
        "event_id": event_id,
        "created_at": now,
        "updated_at": now
    }

    try:
        if event_id:
            # Check if notification for this exact event was already created
            existing = await db.notifications.find_one({"event_id": event_id})
            if existing:
                return str(existing["_id"])

        res = await db.notifications.insert_one(doc)
        return str(res.inserted_id)
    except Exception as e:
        logger.error(f"Error creating notification: {e}")
        return None
