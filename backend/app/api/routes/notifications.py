from fastapi import APIRouter, HTTPException, status, Depends, Query
from datetime import datetime, timezone
from typing import List, Optional
from bson import ObjectId

from app.schemas.all_schemas import (
    NotificationResponse,
    NotificationListResponse,
    NotificationUnreadCountResponse
)
from app.api.deps import get_current_user
from app.database.client import get_database

router = APIRouter(prefix="/notifications", tags=["Notifications & Activity Center"])

def _format_time_ago(dt: datetime) -> str:
    """Helper to convert datetime into human-friendly relative time label."""
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    diff = now - dt
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return "Just now"
    elif seconds < 3600:
        mins = max(1, seconds // 60)
        return f"{mins}m ago"
    elif seconds < 86400:
        hours = max(1, seconds // 3600)
        return f"{hours}h ago"
    else:
        days = max(1, seconds // 86400)
        return f"{days}d ago"

# 1. List Notifications (Paginated with Category/Read Filtering & Relative Timestamps)
@router.get("", response_model=NotificationListResponse)
async def list_notifications(
    category: Optional[str] = Query(None, pattern="^(all|chat|social|food|shopping|system)$"),
    unread_only: bool = Query(False),
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=50),
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        return NotificationListResponse(
            total=0,
            unread_count=0,
            page=page,
            limit=limit,
            has_more=False,
            notifications=[]
        )

    current_uid = current_user["id"]
    query: dict = {"user_id": current_uid}

    if category and category != "all":
        query["category"] = category

    if unread_only:
        query["read"] = False

    total_matching = await db.notifications.count_documents(query)
    total_unread = await db.notifications.count_documents({"user_id": current_uid, "read": False})

    skip = (page - 1) * limit
    cursor = db.notifications.find(query).sort("created_at", -1).skip(skip).limit(limit)

    notifications = []
    async for doc in cursor:
        created_at_dt = doc.get("created_at", datetime.now(timezone.utc))
        time_label = doc.get("time") or _format_time_ago(created_at_dt)
        notifications.append(NotificationResponse(
            id=str(doc["_id"]),
            user_id=doc["user_id"],
            category=doc.get("category", "system"),
            event_type=doc.get("event_type", "general"),
            title=doc.get("title", ""),
            desc=doc.get("desc", ""),
            time=time_label,
            read=doc.get("read", False),
            read_at=doc.get("read_at"),
            metadata=doc.get("metadata", {}),
            created_at=created_at_dt
        ))

    has_more = (skip + len(notifications)) < total_matching

    return NotificationListResponse(
        total=total_matching,
        unread_count=total_unread,
        page=page,
        limit=limit,
        has_more=has_more,
        notifications=notifications
    )

# 2. Get Unread Notifications Count (Used for real-time header badges)
@router.get("/unread-count", response_model=NotificationUnreadCountResponse)
async def get_unread_count(current_user: dict = Depends(get_current_user)):
    db = get_database()
    if db is None:
        return NotificationUnreadCountResponse(unread_count=0)

    count = await db.notifications.count_documents({
        "user_id": current_user["id"],
        "read": False
    })
    return NotificationUnreadCountResponse(unread_count=count)

# 3. Mark Single Notification as Read (Strict Ownership Enforcement)
@router.patch("/{notification_id}/read", response_model=NotificationResponse)
async def mark_notification_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    try:
        obj_id = ObjectId(notification_id)
        query = {"_id": obj_id}
    except Exception:
        query = {"_id": notification_id}

    # Verify notification exists first to enforce 403 vs 404
    notif = await db.notifications.find_one(query)
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    if notif["user_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this notification")

    now = datetime.now(timezone.utc)
    result = await db.notifications.find_one_and_update(
        {"_id": notif["_id"]},
        {"$set": {"read": True, "read_at": now, "updated_at": now}},
        return_document=True
    )

    created_at_dt = result.get("created_at", now)
    return NotificationResponse(
        id=str(result["_id"]),
        user_id=result["user_id"],
        category=result.get("category", "system"),
        event_type=result.get("event_type", "general"),
        title=result.get("title", ""),
        desc=result.get("desc", ""),
        time=result.get("time") or _format_time_ago(created_at_dt),
        read=True,
        read_at=result.get("read_at"),
        metadata=result.get("metadata", {}),
        created_at=created_at_dt
    )

# 4. Mark All Notifications as Read for Current User
@router.post("/mark-all-read", response_model=NotificationUnreadCountResponse)
async def mark_all_notifications_read(current_user: dict = Depends(get_current_user)):
    db = get_database()
    if db is None:
        return NotificationUnreadCountResponse(unread_count=0)

    now = datetime.now(timezone.utc)
    await db.notifications.update_many(
        {"user_id": current_user["id"], "read": False},
        {"$set": {"read": True, "read_at": now, "updated_at": now}}
    )

    return NotificationUnreadCountResponse(unread_count=0)

# 5. Delete / Dismiss Notification (Strict Ownership Enforcement)
@router.delete("/{notification_id}", status_code=status.HTTP_200_OK)
async def delete_notification(
    notification_id: str,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    try:
        obj_id = ObjectId(notification_id)
        query = {"_id": obj_id}
    except Exception:
        query = {"_id": notification_id}

    notif = await db.notifications.find_one(query)
    if not notif:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")

    if notif["user_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to this notification")

    await db.notifications.delete_one({"_id": notif["_id"]})
    return {"status": "deleted", "notification_id": notification_id}

# 6. Clear All Read Notifications (Optional clean-up operation)
@router.delete("/clear-read", status_code=status.HTTP_200_OK)
async def clear_read_notifications(current_user: dict = Depends(get_current_user)):
    db = get_database()
    if db is None:
        return {"status": "cleared", "deleted_count": 0}

    res = await db.notifications.delete_many({
        "user_id": current_user["id"],
        "read": True
    })
    return {"status": "cleared", "deleted_count": res.deleted_count}
