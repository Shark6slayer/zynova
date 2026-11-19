"""
routes/interrelate.py - ZenoSocial Interrelate Feature
Dedicated mutual-consent account linking for couples/partners within ZenoSocial.

Principles:
- Identity: Zen_ID (@username)
- Mutual consent required: User A sends invitation -> User B reviews & accepts/rejects.
- Granular permissions:
  * show_relationship_badge (public/profile relationship badge)
  * share_activity_status (online / viewing status)
  * shared_media_vault_access (private couple album / memories)
- Either user can instantly revoke individual permissions or terminate the entire link.
- Never exposes passwords, OTPs, auth tokens, or private credentials.
- Strictly isolated from ZENOVA Connect and Interconnect.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from bson import ObjectId

from app.schemas.all_schemas import (
    InterrelateRequestPayload,
    InterrelateRespondPayload,
    InterrelatePermissionsUpdatePayload,
    InterrelateStatusResponse,
    UserPublicSummary
)
from app.api.deps import get_current_user
from app.database.client import get_database
from app.core.audit_ledger import record_audit_event

router = APIRouter(prefix="/social/interrelate", tags=["ZenoSocial Interrelate"])

@router.get("/status", response_model=InterrelateStatusResponse)
async def get_interrelate_status(current_user: dict = Depends(get_current_user)):
    db = get_database()
    if db is None:
        return InterrelateStatusResponse(
            is_connected=False,
            my_permissions={"show_relationship_badge": False, "share_activity_status": False, "shared_media_vault_access": False},
            partner_permissions={"show_relationship_badge": False, "share_activity_status": False, "shared_media_vault_access": False},
            pending_requests=[]
        )

    user_id = current_user["id"]

    # Check active link
    active_link = await db.social_interrelate.find_one({
        "status": "active",
        "$or": [{"user_a": user_id}, {"user_b": user_id}]
    })

    # Check pending incoming and outgoing requests
    pending_cursor = db.social_interrelate.find({
        "status": "pending",
        "$or": [{"user_a": user_id}, {"user_b": user_id}]
    })
    pending_requests = []
    async for req in pending_cursor:
        is_sender = (req["user_a"] == user_id)
        other_party_id = req["user_b"] if is_sender else req["user_a"]
        other_user = await db.users.find_one({"_id": ObjectId(other_party_id)})
        pending_requests.append({
            "request_id": str(req["_id"]),
            "is_sender": is_sender,
            "partner_zen_id": other_user.get("username", "") if other_user else "unknown",
            "partner_full_name": other_user.get("full_name", "") if other_user else "",
            "relationship_type": req.get("relationship_type", "partner"),
            "created_at": req.get("created_at")
        })

    if not active_link:
        return InterrelateStatusResponse(
            is_connected=False,
            partner=None,
            relationship_type=None,
            connected_since=None,
            my_permissions={"show_relationship_badge": False, "share_activity_status": False, "shared_media_vault_access": False},
            partner_permissions={"show_relationship_badge": False, "share_activity_status": False, "shared_media_vault_access": False},
            pending_requests=pending_requests
        )

    is_user_a = (active_link["user_a"] == user_id)
    partner_id = active_link["user_b"] if is_user_a else active_link["user_a"]
    partner_user = await db.users.find_one({"_id": ObjectId(partner_id)})

    partner_summary = UserPublicSummary(
        id=partner_id,
        username=partner_user.get("username", "") if partner_user else "partner",
        full_name=partner_user.get("full_name", "") if partner_user else "Partner",
        avatar_url=partner_user.get("avatar_url") if partner_user else None,
        is_verified=partner_user.get("is_verified", False) if partner_user else False
    )

    my_perms = active_link.get("permissions_a" if is_user_a else "permissions_b", {
        "show_relationship_badge": True,
        "share_activity_status": False,
        "shared_media_vault_access": False
    })
    partner_perms = active_link.get("permissions_b" if is_user_a else "permissions_a", {
        "show_relationship_badge": True,
        "share_activity_status": False,
        "shared_media_vault_access": False
    })

    return InterrelateStatusResponse(
        is_connected=True,
        partner=partner_summary,
        relationship_type=active_link.get("relationship_type", "partner"),
        connected_since=active_link.get("connected_since"),
        my_permissions=my_perms,
        partner_permissions=partner_perms,
        pending_requests=pending_requests
    )

@router.post("/request", status_code=status.HTTP_201_CREATED)
async def request_interrelate(
    payload: InterrelateRequestPayload,
    current_user: dict = Depends(get_current_user)
):
    """Sends an Interrelate linking invitation to a partner via Zen_ID."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    user_id = current_user["id"]
    target_zen_id = payload.partner_zen_id.lower().lstrip("@").strip()

    target_user = await db.users.find_one({"username": target_zen_id})
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with Zen_ID '@{target_zen_id}' not found")

    target_id = str(target_user["_id"])
    if target_id == user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot link Interrelate to yourself")

    # Check if already connected to someone
    existing_active = await db.social_interrelate.find_one({
        "status": "active",
        "$or": [{"user_a": user_id}, {"user_b": user_id}]
    })
    if existing_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You already have an active Interrelate connection. Terminate it before linking a new partner.")

    partner_active = await db.social_interrelate.find_one({
        "status": "active",
        "$or": [{"user_a": target_id}, {"user_b": target_id}]
    })
    if partner_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target user already has an active Interrelate connection.")

    # Check existing pending request
    existing_pending = await db.social_interrelate.find_one({
        "status": "pending",
        "$or": [
            {"user_a": user_id, "user_b": target_id},
            {"user_a": target_id, "user_b": user_id}
        ]
    })
    if existing_pending:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An Interrelate request between these accounts is already pending.")

    now = datetime.now(timezone.utc)
    req_doc = {
        "user_a": user_id,
        "user_b": target_id,
        "relationship_type": payload.relationship_type.strip(),
        "note": payload.note,
        "status": "pending",
        "created_at": now,
        "permissions_a": {
            "show_relationship_badge": True,
            "share_activity_status": False,
            "shared_media_vault_access": False
        },
        "permissions_b": {
            "show_relationship_badge": True,
            "share_activity_status": False,
            "shared_media_vault_access": False
        }
    }
    res = await db.social_interrelate.insert_one(req_doc)

    await record_audit_event(
        event_type="INTERRELATE_REQUEST_SENT",
        raw_actor_id=user_id,
        metadata={"target_id": target_id, "zen_id": target_zen_id}
    )

    return {"status": "pending", "request_id": str(res.inserted_id), "message": f"Interrelate request sent to @{target_zen_id}"}

@router.post("/respond")
async def respond_to_interrelate(
    payload: InterrelateRespondPayload,
    current_user: dict = Depends(get_current_user)
):
    """Accepts or rejects an incoming Interrelate request."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    user_id = current_user["id"]
    req = await db.social_interrelate.find_one({"_id": ObjectId(payload.request_id), "user_b": user_id, "status": "pending"})
    if not req:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pending Interrelate request not found")

    now = datetime.now(timezone.utc)
    if payload.action == "reject":
        await db.social_interrelate.update_one(
            {"_id": ObjectId(payload.request_id)},
            {"$set": {"status": "rejected", "responded_at": now}}
        )
        return {"status": "rejected", "message": "Interrelate invitation declined."}

    # Accept: Set active
    await db.social_interrelate.update_one(
        {"_id": ObjectId(payload.request_id)},
        {"$set": {"status": "active", "connected_since": now, "responded_at": now}}
    )

    await record_audit_event(
        event_type="INTERRELATE_MUTUAL_CONSENT_ESTABLISHED",
        raw_actor_id=user_id,
        metadata={"partner_id": req["user_a"]}
    )

    return {"status": "active", "message": "Interrelate connection established with mutual consent!"}

@router.put("/permissions")
async def update_interrelate_permissions(
    payload: InterrelatePermissionsUpdatePayload,
    current_user: dict = Depends(get_current_user)
):
    """Updates user's own granular Interrelate permissions."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    user_id = current_user["id"]
    link = await db.social_interrelate.find_one({
        "status": "active",
        "$or": [{"user_a": user_id}, {"user_b": user_id}]
    })
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active Interrelate connection found")

    is_user_a = (link["user_a"] == user_id)
    perm_field = "permissions_a" if is_user_a else "permissions_b"

    new_perms = {
        "show_relationship_badge": payload.show_relationship_badge,
        "share_activity_status": payload.share_activity_status,
        "shared_media_vault_access": payload.shared_media_vault_access
    }

    await db.social_interrelate.update_one(
        {"_id": link["_id"]},
        {"$set": {perm_field: new_perms, "updated_at": datetime.now(timezone.utc)}}
    )

    await record_audit_event(
        event_type="INTERRELATE_PERMISSIONS_UPDATED",
        raw_actor_id=user_id,
        metadata=new_perms
    )

    return {"status": "updated", "my_permissions": new_perms}

@router.post("/terminate")
async def terminate_interrelate(current_user: dict = Depends(get_current_user)):
    """Instantly severs the Interrelate connection. Takes effect immediately."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    user_id = current_user["id"]
    link = await db.social_interrelate.find_one({
        "status": "active",
        "$or": [{"user_a": user_id}, {"user_b": user_id}]
    })
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active Interrelate connection to terminate")

    now = datetime.now(timezone.utc)
    await db.social_interrelate.update_one(
        {"_id": link["_id"]},
        {"$set": {
            "status": "terminated",
            "terminated_by": user_id,
            "terminated_at": now,
            "permissions_a": {"show_relationship_badge": False, "share_activity_status": False, "shared_media_vault_access": False},
            "permissions_b": {"show_relationship_badge": False, "share_activity_status": False, "shared_media_vault_access": False}
        }}
    )

    await record_audit_event(
        event_type="INTERRELATE_TERMINATED",
        raw_actor_id=user_id,
        metadata={"link_id": str(link["_id"])}
    )

    return {"status": "terminated", "message": "Interrelate connection severed. All shared permissions revoked immediately."}
