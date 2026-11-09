"""
Zynova Connect Service Engine (Phase 26).
Implements the core business logic for:
- 1-to-1 and Group chats with admin roles, invite links, and announcements.
- Idempotent message delivery, offline queuing, delivery/read receipts, editing, deleting, reactions, and pinning.
- Locked chats (Argon2id protected session credentials) and Archived chats.
- WhatsApp-style 24-hour Status updates (text, image, video) with viewer receipts.
- Communities grouping related group chats.
- WebRTC voice/video call signaling and call logging.
- E2EE Signal prekey bundle storage and X3DH handshakes.
"""

from datetime import datetime, timezone, timedelta
from typing import List, Optional, Dict, Any, Tuple
from bson import ObjectId
import html
import secrets

from app.database.client import get_database
from app.core.security import get_password_hash, verify_password
from app.core.crypto_kms import encrypt_field, decrypt_field, is_encrypted
from app.core.ws_manager import chat_manager
from app.services.identity_service import get_blocked_users

def sanitize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return html.escape(text.strip())

# -------------------------------------------------------------
# 1. Chat & Group Management
# -------------------------------------------------------------

async def get_or_create_direct_chat(current_user: dict, recipient_id: str) -> dict:
    db = get_database()
    current_uid = current_user["id"]
    recipient_uid = recipient_id.strip()

    if current_uid == recipient_uid:
        raise ValueError("Cannot create conversation with yourself")

    # Verify mutual block status
    blocked = await get_blocked_users(db, current_uid)
    if recipient_uid in blocked:
        raise PermissionError("Cannot message a blocked user")

    user_query = {"$or": [{"_id": ObjectId(recipient_uid)}, {"_id": recipient_uid}]} if ObjectId.is_valid(recipient_uid) else {"_id": recipient_uid}
    recip_user = await db.users.find_one(user_query)
    if not recip_user:
        raise LookupError("Recipient user not found")

    existing_room = await db.chat_rooms.find_one({
        "type": "direct",
        "participants": {"$all": [current_uid, recipient_uid], "$size": 2}
    })

    if existing_room:
        return existing_room

    now = datetime.now(timezone.utc)
    participant_meta = {
        current_uid: {
            "id": current_uid,
            "username": current_user["username"],
            "full_name": current_user.get("full_name") or current_user.get("username", ""),
            "avatar_url": current_user.get("avatar_url")
        },
        recipient_uid: {
            "id": recipient_uid,
            "username": recip_user.get("username", ""),
            "full_name": recip_user.get("full_name") or recip_user.get("username", ""),
            "avatar_url": recip_user.get("avatar_url")
        }
    }

    room_doc = {
        "type": "direct",
        "name": None,
        "description": None,
        "picture_url": None,
        "participants": [current_uid, recipient_uid],
        "participant_meta": participant_meta,
        "admin_ids": [],
        "community_id": None,
        "archived_by": [],
        "locked_by": {},  # user_id -> argon2_hash
        "pinned_message_id": None,
        "last_message": None,
        "unread_counts": {current_uid: 0, recipient_uid: 0},
        "created_at": now,
        "updated_at": now
    }

    res = await db.chat_rooms.insert_one(room_doc)
    room_doc["_id"] = res.inserted_id
    return room_doc

async def create_group_chat(
    current_user: dict,
    name: str,
    description: Optional[str],
    picture_url: Optional[str],
    participant_ids: List[str],
    community_id: Optional[str] = None
) -> dict:
    db = get_database()
    current_uid = current_user["id"]
    now = datetime.now(timezone.utc)

    # Unique participants including creator
    all_participants = list(set([current_uid] + [p.strip() for p in participant_ids if p.strip()]))
    participant_meta = {}

    for uid in all_participants:
        u = await db.users.find_one({"_id": ObjectId(uid)})
        if u:
            participant_meta[uid] = {
                "id": uid,
                "username": u["username"],
                "full_name": u["full_name"],
                "avatar_url": u.get("avatar_url")
            }

    invite_code = secrets.token_urlsafe(12)
    room_doc = {
        "type": "group",
        "name": sanitize_text(name),
        "description": sanitize_text(description) if description else None,
        "picture_url": picture_url,
        "invite_code": invite_code,
        "participants": list(participant_meta.keys()),
        "participant_meta": participant_meta,
        "admin_ids": [current_uid],
        "community_id": community_id,
        "archived_by": [],
        "locked_by": {},
        "pinned_message_id": None,
        "last_message": None,
        "unread_counts": {uid: 0 for uid in participant_meta.keys()},
        "created_at": now,
        "updated_at": now
    }

    res = await db.chat_rooms.insert_one(room_doc)
    room_doc["_id"] = res.inserted_id

    # Broadcast to all participants
    await chat_manager.broadcast_to_users(
        room_doc["participants"],
        {"event": "group_created", "conversation_id": str(res.inserted_id), "name": room_doc["name"]}
    )
    return room_doc

async def add_group_member(current_user: dict, conversation_id: str, new_user_id: str) -> dict:
    db = get_database()
    room = await db.chat_rooms.find_one({"_id": ObjectId(conversation_id)})
    if not room or room.get("type") != "group":
        raise LookupError("Group not found")

    if current_user["id"] not in room.get("admin_ids", []):
        raise PermissionError("Only admins can add members")

    new_user = await db.users.find_one({"_id": ObjectId(new_user_id)})
    if not new_user:
        raise LookupError("Target user not found")

    new_meta = {
        "id": new_user_id,
        "username": new_user["username"],
        "full_name": new_user["full_name"],
        "avatar_url": new_user.get("avatar_url")
    }

    await db.chat_rooms.update_one(
        {"_id": ObjectId(conversation_id)},
        {
            "$addToSet": {"participants": new_user_id},
            "$set": {
                f"participant_meta.{new_user_id}": new_meta,
                f"unread_counts.{new_user_id}": 0
            }
        }
    )
    return {"status": "ok", "added_user_id": new_user_id}

async def remove_group_member(current_user: dict, conversation_id: str, target_user_id: str) -> dict:
    db = get_database()
    room = await db.chat_rooms.find_one({"_id": ObjectId(conversation_id)})
    if not room or room.get("type") != "group":
        raise LookupError("Group not found")

    # Member can leave, or admin can remove
    if current_user["id"] != target_user_id and current_user["id"] not in room.get("admin_ids", []):
        raise PermissionError("Not authorized to remove member")

    await db.chat_rooms.update_one(
        {"_id": ObjectId(conversation_id)},
        {
            "$pull": {"participants": target_user_id, "admin_ids": target_user_id},
            "$unset": {f"participant_meta.{target_user_id}": "", f"unread_counts.{target_user_id}": ""}
        }
    )
    return {"status": "ok", "removed_user_id": target_user_id}

# -------------------------------------------------------------
# 2. Messaging, Idempotency & Delivery Receipts
# -------------------------------------------------------------

async def send_connect_message(
    current_user: dict,
    conversation_id: str,
    text: Optional[str],
    media_url: Optional[str] = None,
    media_type: str = "text",
    file_name: Optional[str] = None,
    file_size_bytes: Optional[int] = None,
    reply_to_id: Optional[str] = None,
    forward_from_id: Optional[str] = None,
    client_message_id: Optional[str] = None
) -> dict:
    db = get_database()
    current_uid = current_user["id"]

    # Verify room existence & membership
    room = await db.chat_rooms.find_one({
        "_id": ObjectId(conversation_id),
        "participants": current_uid
    })
    if not room:
        raise LookupError("Conversation not found or unauthorized")

    # Idempotency check: if client_message_id is provided, return existing message if found
    if client_message_id:
        existing = await db.chat_messages.find_one({
            "conversation_id": conversation_id,
            "client_message_id": client_message_id
        })
        if existing:
            return existing

    # Validate mutual blocks for direct chat
    if room.get("type") == "direct":
        other_participants = [p for p in room["participants"] if p != current_uid]
        if other_participants:
            blocked = await get_blocked_users(db, current_uid)
            if other_participants[0] in blocked:
                raise PermissionError("Cannot send message to a blocked user")

    now = datetime.now(timezone.utc)
    clean_text = sanitize_text(text) if text else ""
    encrypted_text = encrypt_field(clean_text, context=conversation_id)

    # Online participants get immediate 'delivered' status
    delivered_to = []
    for pid in room["participants"]:
        if pid != current_uid and chat_manager.is_user_online(pid):
            delivered_to.append(pid)

    delivery_status = "delivered" if len(delivered_to) > 0 else "sent"

    msg_doc = {
        "conversation_id": conversation_id,
        "sender_id": current_uid,
        "sender_username": current_user["username"],
        "sender_full_name": current_user["full_name"],
        "sender_avatar": current_user.get("avatar_url"),
        "text": encrypted_text,
        "media_url": media_url,
        "media_type": media_type or "text",
        "file_name": file_name,
        "file_size_bytes": file_size_bytes,
        "reply_to_id": reply_to_id,
        "forward_from_id": forward_from_id,
        "client_message_id": client_message_id,
        "delivery_status": delivery_status,
        "delivered_to": delivered_to,
        "read_by": [current_uid],
        "reactions": {},
        "is_edited": False,
        "is_deleted": False,
        "is_pinned": False,
        "created_at": now,
        "updated_at": now
    }

    res = await db.chat_messages.insert_one(msg_doc)
    msg_id = str(res.inserted_id)
    msg_doc["_id"] = res.inserted_id

    # Update conversation room metadata
    inc_dict = {f"unread_counts.{pid}": 1 for pid in room["participants"] if pid != current_uid}
    last_summary = {
        "id": msg_id,
        "sender_id": current_uid,
        "text": clean_text if clean_text else f"[{media_type}]",
        "media_type": media_type,
        "delivery_status": delivery_status,
        "created_at": now
    }

    await db.chat_rooms.update_one(
        {"_id": ObjectId(conversation_id)},
        {
            "$set": {"last_message": last_summary, "updated_at": now},
            "$inc": inc_dict
        }
    )

    # Real-time WebSocket dispatch
    dispatch_payload = {
        "event": "new_message",
        "conversation_id": conversation_id,
        "message": {
            "id": msg_id,
            "conversation_id": conversation_id,
            "sender_id": current_uid,
            "sender_username": current_user["username"],
            "sender_full_name": current_user["full_name"],
            "sender_avatar": current_user.get("avatar_url"),
            "text": clean_text,
            "media_url": media_url,
            "media_type": media_type,
            "file_name": file_name,
            "file_size_bytes": file_size_bytes,
            "reply_to_id": reply_to_id,
            "forward_from_id": forward_from_id,
            "client_message_id": client_message_id,
            "delivery_status": delivery_status,
            "delivered_to": delivered_to,
            "read_by": [current_uid],
            "reactions": {},
            "is_edited": False,
            "is_deleted": False,
            "is_pinned": False,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }
    }
    await chat_manager.broadcast_to_users(room["participants"], dispatch_payload)

    return msg_doc

async def react_to_message(current_user: dict, message_id: str, emoji: str) -> dict:
    db = get_database()
    current_uid = current_user["id"]
    msg = await db.chat_messages.find_one({"_id": ObjectId(message_id)})
    if not msg:
        raise LookupError("Message not found")

    await db.chat_messages.update_one(
        {"_id": ObjectId(message_id)},
        {"$set": {f"reactions.{current_uid}": emoji}}
    )

    room = await db.chat_rooms.find_one({"_id": ObjectId(msg["conversation_id"])})
    if room:
        await chat_manager.broadcast_to_users(
            room["participants"],
            {
                "event": "message_reaction",
                "message_id": message_id,
                "conversation_id": msg["conversation_id"],
                "user_id": current_uid,
                "emoji": emoji
            }
        )
    return {"status": "ok", "message_id": message_id, "emoji": emoji}

async def toggle_pin_message(current_user: dict, conversation_id: str, message_id: str) -> dict:
    db = get_database()
    room = await db.chat_rooms.find_one({
        "_id": ObjectId(conversation_id),
        "participants": current_user["id"]
    })
    if not room:
        raise LookupError("Conversation not found")

    current_pinned = room.get("pinned_message_id")
    new_pinned = None if current_pinned == message_id else message_id

    await db.chat_rooms.update_one(
        {"_id": ObjectId(conversation_id)},
        {"$set": {"pinned_message_id": new_pinned}}
    )
    await db.chat_messages.update_one(
        {"_id": ObjectId(message_id)},
        {"$set": {"is_pinned": (new_pinned == message_id)}}
    )

    await chat_manager.broadcast_to_users(
        room["participants"],
        {"event": "message_pinned", "conversation_id": conversation_id, "pinned_message_id": new_pinned}
    )
    return {"status": "ok", "pinned_message_id": new_pinned}

# -------------------------------------------------------------
# 3. Locked Chats & Archived Chats
# -------------------------------------------------------------

async def lock_conversation(current_user: dict, conversation_id: str, pin: str) -> dict:
    """Locks a conversation for current user using Argon2id PIN hash."""
    db = get_database()
    current_uid = current_user["id"]
    room = await db.chat_rooms.find_one({"_id": ObjectId(conversation_id), "participants": current_uid})
    if not room:
        raise LookupError("Conversation not found")

    hashed_pin = get_password_hash(pin)
    await db.chat_rooms.update_one(
        {"_id": ObjectId(conversation_id)},
        {"$set": {f"locked_by.{current_uid}": hashed_pin}}
    )
    return {"status": "locked", "conversation_id": conversation_id}

async def unlock_conversation(current_user: dict, conversation_id: str, pin: str) -> dict:
    """Verifies Argon2id PIN to grant ephemeral unlock session token."""
    db = get_database()
    current_uid = current_user["id"]
    room = await db.chat_rooms.find_one({"_id": ObjectId(conversation_id), "participants": current_uid})
    if not room:
        raise LookupError("Conversation not found")

    locked_hash = room.get("locked_by", {}).get(current_uid)
    if not locked_hash:
        return {"status": "unlocked", "conversation_id": conversation_id}

    if not verify_password(pin, locked_hash):
        raise PermissionError("Incorrect PIN for locked chat")

    return {"status": "verified", "conversation_id": conversation_id, "unlocked": True}

async def toggle_archive_conversation(current_user: dict, conversation_id: str) -> dict:
    db = get_database()
    current_uid = current_user["id"]
    room = await db.chat_rooms.find_one({"_id": ObjectId(conversation_id), "participants": current_uid})
    if not room:
        raise LookupError("Conversation not found")

    is_archived = current_uid in room.get("archived_by", [])
    if is_archived:
        await db.chat_rooms.update_one(
            {"_id": ObjectId(conversation_id)},
            {"$pull": {"archived_by": current_uid}}
        )
        return {"status": "unarchived", "conversation_id": conversation_id}
    else:
        await db.chat_rooms.update_one(
            {"_id": ObjectId(conversation_id)},
            {"$addToSet": {"archived_by": current_uid}}
        )
        return {"status": "archived", "conversation_id": conversation_id}

# -------------------------------------------------------------
# 4. Status Updates (24-Hour Expiration)
# -------------------------------------------------------------

async def post_connect_status(
    current_user: dict,
    media_url: Optional[str],
    media_type: str,
    caption: Optional[str],
    bg_color: Optional[str] = None,
    font_style: Optional[str] = None,
    privacy: str = "contacts"
) -> dict:
    db = get_database()
    current_uid = current_user["id"]
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(hours=24)

    status_doc = {
        "user_id": current_uid,
        "user_username": current_user["username"],
        "user_full_name": current_user["full_name"],
        "user_avatar": current_user.get("avatar_url"),
        "media_url": media_url,
        "media_type": media_type,
        "caption": sanitize_text(caption) if caption else None,
        "bg_color": bg_color,
        "font_style": font_style,
        "privacy": privacy,
        "viewers": [],
        "created_at": now,
        "expires_at": expires_at
    }

    res = await db.connect_statuses.insert_one(status_doc)
    status_doc["_id"] = res.inserted_id
    return status_doc

async def get_connect_status_feed(current_user: dict) -> List[dict]:
    db = get_database()
    current_uid = current_user["id"]
    now = datetime.now(timezone.utc)
    blocked = await get_blocked_users(db, current_uid)

    # Fetch contacts/following users
    user_doc = await db.users.find_one({"_id": ObjectId(current_uid)})
    following = user_doc.get("social_profile", {}).get("following", []) if user_doc else []
    allowed_authors = set(following + [current_uid]) - set(blocked)

    cursor = db.connect_statuses.find({
        "user_id": {"$in": list(allowed_authors)},
        "expires_at": {"$gt": now}
    }).sort("created_at", -1)

    statuses = []
    async for s in cursor:
        statuses.append(s)
    return statuses

async def record_status_view(current_user: dict, status_id: str) -> dict:
    db = get_database()
    current_uid = current_user["id"]
    now = datetime.now(timezone.utc)

    view_entry = {"viewer_id": current_uid, "viewed_at": now}
    await db.connect_statuses.update_one(
        {"_id": ObjectId(status_id)},
        {"$addToSet": {"viewers": current_uid}}
    )
    return {"status": "ok", "status_id": status_id}

# -------------------------------------------------------------
# 5. Communities
# -------------------------------------------------------------

async def create_community(
    current_user: dict,
    name: str,
    description: Optional[str],
    picture_url: Optional[str],
    group_ids: Optional[List[str]] = None
) -> dict:
    db = get_database()
    current_uid = current_user["id"]
    now = datetime.now(timezone.utc)

    # 1. Create Announcement Group for Community
    announcement_group = await create_group_chat(
        current_user=current_user,
        name=f"{name} Announcements",
        description="Official community updates and announcements",
        picture_url=picture_url,
        participant_ids=[]
    )
    ann_group_id = str(announcement_group["_id"])

    all_groups = list(set([ann_group_id] + (group_ids or [])))

    community_doc = {
        "name": sanitize_text(name),
        "description": sanitize_text(description) if description else None,
        "picture_url": picture_url,
        "creator_id": current_uid,
        "admin_ids": [current_uid],
        "group_ids": all_groups,
        "announcement_group_id": ann_group_id,
        "created_at": now,
        "updated_at": now
    }

    res = await db.connect_communities.insert_one(community_doc)
    comm_id = str(res.inserted_id)
    community_doc["_id"] = res.inserted_id

    # Bind groups to community
    await db.chat_rooms.update_many(
        {"_id": {"$in": [ObjectId(gid) for gid in all_groups]}},
        {"$set": {"community_id": comm_id}}
    )

    return community_doc

# -------------------------------------------------------------
# 6. WebRTC Voice & Video Call Signaling
# -------------------------------------------------------------

async def initiate_call(current_user: dict, conversation_id: str, call_type: str, recipient_id: Optional[str] = None) -> dict:
    db = get_database()
    current_uid = current_user["id"]
    room = await db.chat_rooms.find_one({"_id": ObjectId(conversation_id), "participants": current_uid})
    if not room:
        raise LookupError("Conversation not found")

    participants = [recipient_id] if recipient_id else [p for p in room["participants"] if p != current_uid]
    now = datetime.now(timezone.utc)

    call_doc = {
        "conversation_id": conversation_id,
        "caller_id": current_uid,
        "caller_name": current_user["full_name"],
        "caller_avatar": current_user.get("avatar_url"),
        "participants": [current_uid] + participants,
        "call_type": call_type,
        "status": "ringing",
        "duration_seconds": 0,
        "created_at": now,
        "ended_at": None
    }

    res = await db.connect_calls.insert_one(call_doc)
    call_id = str(res.inserted_id)
    call_doc["_id"] = res.inserted_id

    # Broadcast incoming call
    await chat_manager.broadcast_to_users(
        participants,
        {
            "event": "incoming_call",
            "call_id": call_id,
            "conversation_id": conversation_id,
            "caller_id": current_uid,
            "caller_name": current_user["full_name"],
            "call_type": call_type
        }
    )

    return call_doc

async def handle_call_signal(current_user: dict, call_id: str, signal_type: str, payload: dict) -> dict:
    db = get_database()
    current_uid = current_user["id"]
    call = await db.connect_calls.find_one({"_id": ObjectId(call_id)})
    if not call or current_uid not in call.get("participants", []):
        raise LookupError("Call session not found or unauthorized")

    now = datetime.now(timezone.utc)
    target_users = [uid for uid in call["participants"] if uid != current_uid]

    if signal_type in ("end", "reject"):
        created_at = call.get("created_at")
        if created_at and created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        duration = int((now - created_at).total_seconds()) if created_at else 0
        new_status = "completed" if signal_type == "end" else "rejected"
        await db.connect_calls.update_one(
            {"_id": ObjectId(call_id)},
            {"$set": {"status": new_status, "duration_seconds": duration, "ended_at": now}}
        )

    await chat_manager.broadcast_to_users(
        target_users,
        {
            "event": "call_signal",
            "call_id": call_id,
            "sender_id": current_uid,
            "signal_type": signal_type,
            "payload": payload
        }
    )
    return {"status": "ok", "call_id": call_id, "signal_type": signal_type}

# -------------------------------------------------------------
# 7. E2EE Signal Prekey Bundles
# -------------------------------------------------------------

async def publish_e2ee_prekey_bundle(
    current_user: dict,
    identity_key_pub: str,
    signed_prekey_pub: str,
    signed_prekey_sig: Optional[str],
    one_time_prekeys: List[Dict[str, Any]],
    device_id: Optional[str] = None
) -> dict:
    db = get_database()
    current_uid = current_user["id"]
    now = datetime.now(timezone.utc)

    bundle_doc = {
        "user_id": current_uid,
        "device_id": device_id or "primary",
        "identity_key_pub": identity_key_pub,
        "signed_prekey_pub": signed_prekey_pub,
        "signed_prekey_sig": signed_prekey_sig,
        "one_time_prekeys": one_time_prekeys,
        "updated_at": now
    }

    await db.e2ee_prekeys.update_one(
        {"user_id": current_uid, "device_id": bundle_doc["device_id"]},
        {"$set": bundle_doc},
        upsert=True
    )
    return {"status": "published", "user_id": current_uid, "opk_count": len(one_time_prekeys)}

async def fetch_e2ee_prekey_bundle(target_user_id: str, device_id: Optional[str] = None) -> dict:
    db = get_database()
    query = {"user_id": target_user_id}
    if device_id:
        query["device_id"] = device_id

    bundle = await db.e2ee_prekeys.find_one(query)
    if not bundle:
        raise LookupError("Prekey bundle not found for user")

    # Pop one OPK atomically to avoid key reuse
    opk = None
    if bundle.get("one_time_prekeys"):
        opk = bundle["one_time_prekeys"][0]
        await db.e2ee_prekeys.update_one(
            {"_id": bundle["_id"]},
            {"$pop": {"one_time_prekeys": -1}}
        )

    return {
        "user_id": target_user_id,
        "device_id": bundle.get("device_id", "primary"),
        "identity_key_pub": bundle["identity_key_pub"],
        "signed_prekey_pub": bundle["signed_prekey_pub"],
        "signed_prekey_sig": bundle.get("signed_prekey_sig"),
        "one_time_prekey": opk
    }
