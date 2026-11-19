"""
routes/interconnect.py - ZENOVA Connect Interconnect Feature
Dedicated mutual-consent connection within ZENOVA Connect (Phone identity).

Principles:
- Identity: Phone-verified Connect user
- Mutual consent required: User A invites -> User B reviews & accepts/rejects.
- Granular permissions:
  * share_online_presence: boolean
  * allow_conversation_sync: boolean
  * authorized_conversation_ids: List of specific conversations granted sync access
  * shared_notes_access: boolean
- Either user can instantly revoke permissions or disconnect.
- Strictly isolated from ZenoSocial and Interrelate.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from bson import ObjectId

from app.schemas.all_schemas import (
    InterconnectInvitePayload,
    InterconnectRespondPayload,
    InterconnectPermissionsPayload,
    InterconnectStatusResponse
)
from app.api.deps import get_current_user
from app.database.client import get_database
from app.core.audit_ledger import record_audit_event

router = APIRouter(prefix="/chat/interconnect", tags=["ZENOVA Connect Interconnect"])

def mask_phone_number(phone: str) -> str:
    cleaned = phone.strip()
    if len(cleaned) <= 4:
        return "****"
    return cleaned[:2] + "*" * (len(cleaned) - 6) + cleaned[-4:]

@router.get("/status", response_model=InterconnectStatusResponse)
async def get_interconnect_status(current_user: dict = Depends(get_current_user)):
    db = get_database()
    if db is None:
        return InterconnectStatusResponse(
            is_connected=False,
            my_permissions={"share_online_presence": False, "allow_conversation_sync": False, "shared_notes_access": False},
            partner_permissions={"share_online_presence": False, "allow_conversation_sync": False, "shared_notes_access": False},
            pending_invites=[]
        )

    user_id = current_user["id"]

    # Check active connection
    active_link = await db.connect_interconnect.find_one({
        "status": "active",
        "$or": [{"user_a": user_id}, {"user_b": user_id}]
    })

    # Check pending invites
    pending_cursor = db.connect_interconnect.find({
        "status": "pending",
        "$or": [{"user_a": user_id}, {"user_b": user_id}]
    })
    pending_invites = []
    async for inv in pending_cursor:
        is_sender = (inv["user_a"] == user_id)
        other_id = inv["user_b"] if is_sender else inv["user_a"]
        other_user = await db.users.find_one({"_id": ObjectId(other_id)})
        other_phone = other_user.get("verified_phone") or other_user.get("phone_number", "")
        pending_invites.append({
            "invite_id": str(inv["_id"]),
            "is_sender": is_sender,
            "partner_phone_masked": mask_phone_number(other_phone) if other_phone else "Unknown",
            "partner_name": other_user.get("full_name", "") if other_user else "",
            "created_at": inv.get("created_at")
        })

    if not active_link:
        return InterconnectStatusResponse(
            is_connected=False,
            partner_user_id=None,
            partner_phone_masked=None,
            connected_since=None,
            my_permissions={"share_online_presence": False, "allow_conversation_sync": False, "shared_notes_access": False},
            partner_permissions={"share_online_presence": False, "allow_conversation_sync": False, "shared_notes_access": False},
            pending_invites=pending_invites
        )

    is_user_a = (active_link["user_a"] == user_id)
    partner_id = active_link["user_b"] if is_user_a else active_link["user_a"]
    partner_user = await db.users.find_one({"_id": ObjectId(partner_id)})
    partner_phone = partner_user.get("verified_phone") or partner_user.get("phone_number", "") if partner_user else ""

    my_perms = active_link.get("permissions_a" if is_user_a else "permissions_b", {
        "share_online_presence": True,
        "allow_conversation_sync": False,
        "authorized_conversation_ids": [],
        "shared_notes_access": False
    })
    partner_perms = active_link.get("permissions_b" if is_user_a else "permissions_a", {
        "share_online_presence": True,
        "allow_conversation_sync": False,
        "authorized_conversation_ids": [],
        "shared_notes_access": False
    })

    return InterconnectStatusResponse(
        is_connected=True,
        partner_user_id=partner_id,
        partner_phone_masked=mask_phone_number(partner_phone) if partner_phone else "Private",
        connected_since=active_link.get("connected_since"),
        my_permissions=my_perms,
        partner_permissions=partner_perms,
        pending_invites=pending_invites
    )

@router.post("/invite", status_code=status.HTTP_201_CREATED)
async def send_interconnect_invite(
    payload: InterconnectInvitePayload,
    current_user: dict = Depends(get_current_user)
):
    """Sends an Interconnect invitation to a verified Connect contact by phone number."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    user_id = current_user["id"]
    clean_phone = payload.target_phone_number.strip().replace(" ", "").replace("-", "")

    # Look up target user by verified phone
    target_user = await db.users.find_one({
        "$or": [{"verified_phone": clean_phone}, {"phone_number": clean_phone}]
    })
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No registered Connect user found with this verified mobile number")

    target_id = str(target_user["_id"])
    if target_id == user_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot connect Interconnect to your own number")

    # Check existing active connection
    existing_active = await db.connect_interconnect.find_one({
        "status": "active",
        "$or": [{"user_a": user_id}, {"user_b": user_id}]
    })
    if existing_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="You already have an active Interconnect connection. Disconnect it before establishing a new one.")

    partner_active = await db.connect_interconnect.find_one({
        "status": "active",
        "$or": [{"user_a": target_id}, {"user_b": target_id}]
    })
    if partner_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target user already has an active Interconnect connection.")

    # Check existing pending invite
    existing_pending = await db.connect_interconnect.find_one({
        "status": "pending",
        "$or": [
            {"user_a": user_id, "user_b": target_id},
            {"user_a": target_id, "user_b": user_id}
        ]
    })
    if existing_pending:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="An Interconnect invitation between these contacts is already pending.")

    now = datetime.now(timezone.utc)
    inv_doc = {
        "user_a": user_id,
        "user_b": target_id,
        "target_phone": clean_phone,
        "note": payload.note,
        "status": "pending",
        "created_at": now,
        "permissions_a": {
            "share_online_presence": True,
            "allow_conversation_sync": False,
            "authorized_conversation_ids": [],
            "shared_notes_access": False
        },
        "permissions_b": {
            "share_online_presence": True,
            "allow_conversation_sync": False,
            "authorized_conversation_ids": [],
            "shared_notes_access": False
        }
    }
    res = await db.connect_interconnect.insert_one(inv_doc)

    await record_audit_event(
        event_type="INTERCONNECT_INVITE_SENT",
        raw_actor_id=user_id,
        metadata={"target_id": target_id, "phone_masked": mask_phone_number(clean_phone)}
    )

    return {"status": "pending", "invite_id": str(res.inserted_id), "message": f"Interconnect invitation sent to {mask_phone_number(clean_phone)}"}

@router.post("/respond")
async def respond_to_interconnect(
    payload: InterconnectRespondPayload,
    current_user: dict = Depends(get_current_user)
):
    """Accepts or rejects an incoming Interconnect invitation."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    user_id = current_user["id"]
    inv = await db.connect_interconnect.find_one({"_id": ObjectId(payload.invite_id), "user_b": user_id, "status": "pending"})
    if not inv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Pending Interconnect invitation not found")

    now = datetime.now(timezone.utc)
    if payload.action == "reject":
        await db.connect_interconnect.update_one(
            {"_id": ObjectId(payload.invite_id)},
            {"$set": {"status": "rejected", "responded_at": now}}
        )
        return {"status": "rejected", "message": "Interconnect invitation declined."}

    # Accept: Set active
    await db.connect_interconnect.update_one(
        {"_id": ObjectId(payload.invite_id)},
        {"$set": {"status": "active", "connected_since": now, "responded_at": now}}
    )

    await record_audit_event(
        event_type="INTERCONNECT_MUTUAL_CONSENT_ESTABLISHED",
        raw_actor_id=user_id,
        metadata={"partner_id": inv["user_a"]}
    )

    return {"status": "active", "message": "Interconnect connection established with mutual consent!"}

@router.put("/permissions")
async def update_interconnect_permissions(
    payload: InterconnectPermissionsPayload,
    current_user: dict = Depends(get_current_user)
):
    """Updates user's own granular Connect Interconnect permissions."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    user_id = current_user["id"]
    link = await db.connect_interconnect.find_one({
        "status": "active",
        "$or": [{"user_a": user_id}, {"user_b": user_id}]
    })
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active Interconnect connection found")

    is_user_a = (link["user_a"] == user_id)
    perm_field = "permissions_a" if is_user_a else "permissions_b"

    new_perms = {
        "share_online_presence": payload.share_online_presence,
        "allow_conversation_sync": payload.allow_conversation_sync,
        "authorized_conversation_ids": payload.authorized_conversation_ids,
        "shared_notes_access": payload.shared_notes_access
    }

    await db.connect_interconnect.update_one(
        {"_id": link["_id"]},
        {"$set": {perm_field: new_perms, "updated_at": datetime.now(timezone.utc)}}
    )

    await record_audit_event(
        event_type="INTERCONNECT_PERMISSIONS_UPDATED",
        raw_actor_id=user_id,
        metadata={"presence": new_perms["share_online_presence"], "sync": new_perms["allow_conversation_sync"]}
    )

    return {"status": "updated", "my_permissions": new_perms}

@router.post("/disconnect")
async def disconnect_interconnect(current_user: dict = Depends(get_current_user)):
    """Instantly severs the Connect Interconnect connection."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    user_id = current_user["id"]
    link = await db.connect_interconnect.find_one({
        "status": "active",
        "$or": [{"user_a": user_id}, {"user_b": user_id}]
    })
    if not link:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No active Interconnect connection to disconnect")

    now = datetime.now(timezone.utc)
    await db.connect_interconnect.update_one(
        {"_id": link["_id"]},
        {"$set": {
            "status": "disconnected",
            "disconnected_by": user_id,
            "disconnected_at": now,
            "permissions_a": {"share_online_presence": False, "allow_conversation_sync": False, "authorized_conversation_ids": [], "shared_notes_access": False},
            "permissions_b": {"share_online_presence": False, "allow_conversation_sync": False, "authorized_conversation_ids": [], "shared_notes_access": False}
        }}
    )

    await record_audit_event(
        event_type="INTERCONNECT_DISCONNECTED",
        raw_actor_id=user_id,
        metadata={"link_id": str(link["_id"])}
    )

    return {"status": "disconnected", "message": "Interconnect connection severed. All shared permissions revoked immediately."}
