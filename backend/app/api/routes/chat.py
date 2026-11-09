"""
API Routes for Zynova Connect Communication Platform (Phase 26).
Mounts endpoints for:
- 1-to-1 conversations & Group chats with admin moderation and invites.
- Real-time messages with delivery/read receipts, replies, forwards, media, pinning, and reactions.
- Locked chats (Argon2id protected) and Archived chats.
- WhatsApp-style 24-hour Status updates (text, image, video).
- Communities organizing groups.
- WebRTC Voice & Video call signaling and history.
- E2EE Signal prekey bundle management.
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query, WebSocket, WebSocketDisconnect
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from bson import ObjectId
import html

from app.schemas.all_schemas import (
    UserPublicSummary,
    ChatConversationCreate,
    ChatConversationResponse,
    ChatMessageCreate,
    ChatMessageUpdate,
    ChatMessageResponse,
    LastMessageSummary,
    GroupCreatePayload,
    GroupUpdatePayload,
    GroupMemberActionPayload,
    CommunityCreatePayload,
    CommunityResponse,
    ConnectStatusCreatePayload,
    ConnectStatusResponse,
    LockChatPayload,
    UnlockChatPayload,
    CallInitiatePayload,
    CallSignalPayload,
    CallHistoryResponse,
    E2EEPrekeyBundlePayload,
    E2EEPrekeyBundleResponse,
    MessageReactionPayload
)
from app.api.deps import get_current_user
from app.database.client import get_database
from app.core.rate_limit import check_chat_user_rate_limit
from app.core.ws_manager import chat_manager
from app.core.security import decode_token
from app.core.crypto_kms import encrypt_field, decrypt_field, is_encrypted
from app.services import connect_service

router = APIRouter(prefix="/chat", tags=["Zynova Connect Communication Platform"])

def sanitize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return html.escape(text.strip())

# -------------------------------------------------------------
# 1. Contact Discovery & User Presence
# -------------------------------------------------------------

@router.get("/users/search", response_model=List[UserPublicSummary])
async def search_users(
    q: str = Query(..., min_length=1, max_length=50),
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        return []

    regex_pattern = {"$regex": q, "$options": "i"}
    cursor = db.users.find({
        "_id": {"$ne": ObjectId(current_user["id"])},
        "$or": [{"username": regex_pattern}, {"full_name": regex_pattern}]
    }).limit(15)

    results = []
    async for u in cursor:
        results.append(UserPublicSummary(
            id=str(u["_id"]),
            username=u.get("username", ""),
            full_name=u.get("full_name") or u.get("username", ""),
            avatar_url=u.get("avatar_url")
        ))
    return results

@router.get("/users/{user_id}/presence")
async def get_user_presence(user_id: str, current_user: dict = Depends(get_current_user)):
    return chat_manager.get_user_status(user_id)

# -------------------------------------------------------------
# 2. Conversation & Group Management
# -------------------------------------------------------------

@router.post("/conversations", response_model=ChatConversationResponse, status_code=status.HTTP_200_OK)
async def get_or_create_conversation(
    req: ChatConversationCreate,
    current_user: dict = Depends(get_current_user)
):
    try:
        room = await connect_service.get_or_create_direct_chat(current_user, req.recipient_id)
        current_uid = current_user["id"]
        unread_for_user = room.get("unread_counts", {}).get(current_uid, 0)
        last_m = room.get("last_message")
        return ChatConversationResponse(
            id=str(room["_id"]),
            type=room.get("type", "direct"),
            name=room.get("name"),
            description=room.get("description"),
            picture_url=room.get("picture_url"),
            participants=room["participants"],
            participant_meta=room.get("participant_meta", {}),
            admin_ids=room.get("admin_ids", []),
            community_id=room.get("community_id"),
            is_archived=current_uid in room.get("archived_by", []),
            is_locked=current_uid in room.get("locked_by", {}),
            pinned_message_id=room.get("pinned_message_id"),
            last_message=last_m,
            unread_count=unread_for_user,
            created_at=room.get("created_at", datetime.now(timezone.utc)),
            updated_at=room.get("updated_at", datetime.now(timezone.utc))
        )
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except (ValueError, PermissionError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.post("/groups", response_model=ChatConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_group(
    payload: GroupCreatePayload,
    current_user: dict = Depends(get_current_user)
):
    room = await connect_service.create_group_chat(
        current_user=current_user,
        name=payload.name,
        description=payload.description,
        picture_url=payload.picture_url,
        participant_ids=payload.participant_ids,
        community_id=payload.community_id
    )
    current_uid = current_user["id"]
    return ChatConversationResponse(
        id=str(room["_id"]),
        type="group",
        name=room.get("name"),
        description=room.get("description"),
        picture_url=room.get("picture_url"),
        participants=room["participants"],
        participant_meta=room.get("participant_meta", {}),
        admin_ids=room.get("admin_ids", []),
        community_id=room.get("community_id"),
        is_archived=False,
        is_locked=False,
        pinned_message_id=None,
        last_message=None,
        unread_count=0,
        created_at=room["created_at"],
        updated_at=room["updated_at"]
    )

@router.post("/groups/{conversation_id}/members", status_code=status.HTTP_200_OK)
async def add_member_to_group(
    conversation_id: str,
    payload: GroupMemberActionPayload,
    current_user: dict = Depends(get_current_user)
):
    try:
        return await connect_service.add_group_member(current_user, conversation_id, payload.user_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

@router.delete("/groups/{conversation_id}/members/{user_id}", status_code=status.HTTP_200_OK)
async def remove_member_from_group(
    conversation_id: str,
    user_id: str,
    current_user: dict = Depends(get_current_user)
):
    try:
        return await connect_service.remove_group_member(current_user, conversation_id, user_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

@router.get("/conversations", response_model=List[ChatConversationResponse])
async def list_conversations(
    limit: int = Query(50, ge=1, le=100),
    archived: bool = Query(False, description="Filter archived conversations"),
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        return []

    current_uid = current_user["id"]
    query = {"participants": current_uid}
    if archived:
        query["archived_by"] = current_uid
    else:
        query["archived_by"] = {"$ne": current_uid}

    cursor = db.chat_rooms.find(query).sort("updated_at", -1).limit(limit)
    results = []
    async for room in cursor:
        unread_for_user = room.get("unread_counts", {}).get(current_uid, 0)
        last_m = room.get("last_message")
        if last_m and isinstance(last_m, dict):
            raw_last_text = last_m.get("text", "")
            if is_encrypted(raw_last_text):
                conv_id = str(room["_id"])
                last_m = {**last_m, "text": decrypt_field(raw_last_text, context=conv_id)}

        results.append(ChatConversationResponse(
            id=str(room["_id"]),
            type=room.get("type", "direct"),
            name=room.get("name"),
            description=room.get("description"),
            picture_url=room.get("picture_url"),
            participants=room["participants"],
            participant_meta=room.get("participant_meta", {}),
            admin_ids=room.get("admin_ids", []),
            community_id=room.get("community_id"),
            is_archived=current_uid in room.get("archived_by", []),
            is_locked=current_uid in room.get("locked_by", {}),
            pinned_message_id=room.get("pinned_message_id"),
            last_message=last_m,
            unread_count=unread_for_user,
            created_at=room.get("created_at", datetime.now(timezone.utc)),
            updated_at=room.get("updated_at", datetime.now(timezone.utc))
        ))
    return results

# -------------------------------------------------------------
# 3. Message Lifecycle, Delivery Receipts & Reactions
# -------------------------------------------------------------

@router.post("/conversations/{conversation_id}/messages", response_model=ChatMessageResponse, status_code=status.HTTP_201_CREATED)
async def send_message(
    conversation_id: str,
    msg_in: ChatMessageCreate,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    current_uid = current_user["id"]
    check_chat_user_rate_limit(current_uid)

    try:
        msg_doc = await connect_service.send_connect_message(
            current_user=current_user,
            conversation_id=conversation_id,
            text=msg_in.text,
            media_url=msg_in.media_url,
            media_type=msg_in.media_type or "text",
            file_name=msg_in.file_name,
            file_size_bytes=msg_in.file_size_bytes,
            reply_to_id=msg_in.reply_to_id,
            forward_from_id=msg_in.forward_from_id,
            client_message_id=msg_in.client_message_id
        )

        raw_text = msg_doc.get("text", "")
        decrypted = decrypt_field(raw_text, context=conversation_id) if is_encrypted(raw_text) else raw_text

        return ChatMessageResponse(
            id=str(msg_doc["_id"]),
            conversation_id=conversation_id,
            sender_id=current_uid,
            sender_username=current_user["username"],
            sender_full_name=current_user["full_name"],
            sender_avatar=current_user.get("avatar_url"),
            text=decrypted,
            media_url=msg_doc.get("media_url"),
            media_type=msg_doc.get("media_type", "text"),
            file_name=msg_doc.get("file_name"),
            file_size_bytes=msg_doc.get("file_size_bytes"),
            reply_to_id=msg_doc.get("reply_to_id"),
            forward_from_id=msg_doc.get("forward_from_id"),
            client_message_id=msg_doc.get("client_message_id"),
            created_at=msg_doc["created_at"],
            updated_at=msg_doc["updated_at"],
            is_edited=msg_doc.get("is_edited", False),
            is_deleted=msg_doc.get("is_deleted", False),
            is_pinned=msg_doc.get("is_pinned", False),
            delivery_status=msg_doc.get("delivery_status", "sent"),
            delivered_to=msg_doc.get("delivered_to", []),
            read_by=msg_doc.get("read_by", [current_uid]),
            reactions=msg_doc.get("reactions", {})
        )
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/conversations/{conversation_id}/messages", response_model=List[ChatMessageResponse])
async def get_conversation_messages(
    conversation_id: str,
    limit: int = Query(40, ge=1, le=100),
    before: Optional[str] = Query(None),
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    current_uid = current_user["id"]
    room = await db.chat_rooms.find_one({"_id": ObjectId(conversation_id), "participants": current_uid})
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found or unauthorized")

    query: dict = {"conversation_id": conversation_id}
    if before:
        try:
            cursor_dt = datetime.fromisoformat(before)
            query["created_at"] = {"$lt": cursor_dt}
        except Exception:
            pass

    cursor = db.chat_messages.find(query).sort("created_at", -1).limit(limit)
    messages = []
    async for msg in cursor:
        raw_text = msg.get("text", "")
        decrypted = decrypt_field(raw_text, context=conversation_id) if is_encrypted(raw_text) else raw_text
        messages.append(ChatMessageResponse(
            id=str(msg["_id"]),
            conversation_id=msg["conversation_id"],
            sender_id=msg["sender_id"],
            sender_username=msg.get("sender_username", ""),
            sender_full_name=msg.get("sender_full_name", ""),
            sender_avatar=msg.get("sender_avatar"),
            text=decrypted,
            media_url=msg.get("media_url"),
            media_type=msg.get("media_type", "text"),
            file_name=msg.get("file_name"),
            file_size_bytes=msg.get("file_size_bytes"),
            reply_to_id=msg.get("reply_to_id"),
            forward_from_id=msg.get("forward_from_id"),
            client_message_id=msg.get("client_message_id"),
            created_at=msg["created_at"],
            updated_at=msg.get("updated_at", msg["created_at"]),
            is_edited=msg.get("is_edited", False),
            is_deleted=msg.get("is_deleted", False),
            is_pinned=msg.get("is_pinned", False),
            delivery_status=msg.get("delivery_status", "sent"),
            delivered_to=msg.get("delivered_to", []),
            read_by=msg.get("read_by", []),
            reactions=msg.get("reactions", {})
        ))

    messages.reverse()
    return messages

@router.patch("/messages/{message_id}", response_model=ChatMessageResponse)
async def edit_message(
    message_id: str,
    update_in: ChatMessageUpdate,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    msg = await db.chat_messages.find_one({"_id": ObjectId(message_id)})
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    if msg["sender_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot edit another user's message")

    if msg.get("is_deleted", False):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot edit a deleted message")

    clean_text = sanitize_text(update_in.text)
    now = datetime.now(timezone.utc)
    conv_id = msg["conversation_id"]
    encrypted_edited = encrypt_field(clean_text, context=conv_id)

    await db.chat_messages.update_one(
        {"_id": ObjectId(message_id)},
        {"$set": {"text": encrypted_edited, "is_edited": True, "updated_at": now}}
    )

    room = await db.chat_rooms.find_one({"_id": ObjectId(conv_id)})
    participants = room["participants"] if room else [current_user["id"]]

    response_msg = ChatMessageResponse(
        id=message_id,
        conversation_id=conv_id,
        sender_id=msg["sender_id"],
        sender_username=msg.get("sender_username", ""),
        sender_full_name=msg.get("sender_full_name", ""),
        sender_avatar=msg.get("sender_avatar"),
        text=clean_text,
        media_url=msg.get("media_url"),
        media_type=msg.get("media_type", "text"),
        file_name=msg.get("file_name"),
        file_size_bytes=msg.get("file_size_bytes"),
        reply_to_id=msg.get("reply_to_id"),
        forward_from_id=msg.get("forward_from_id"),
        client_message_id=msg.get("client_message_id"),
        created_at=msg["created_at"],
        updated_at=now,
        is_edited=True,
        is_deleted=False,
        is_pinned=msg.get("is_pinned", False),
        delivery_status=msg.get("delivery_status", "sent"),
        delivered_to=msg.get("delivered_to", []),
        read_by=msg.get("read_by", []),
        reactions=msg.get("reactions", {})
    )

    await chat_manager.broadcast_to_users(
        participants,
        {"event": "message_edited", "conversation_id": conv_id, "message": response_msg.model_dump(mode="json")}
    )
    return response_msg

@router.delete("/messages/{message_id}", response_model=ChatMessageResponse)
async def delete_message(message_id: str, current_user: dict = Depends(get_current_user)):
    db = get_database()
    msg = await db.chat_messages.find_one({"_id": ObjectId(message_id)})
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    if msg["sender_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete another user's message")

    now = datetime.now(timezone.utc)
    deleted_text = "This message was deleted."
    await db.chat_messages.update_one(
        {"_id": ObjectId(message_id)},
        {"$set": {"text": deleted_text, "is_deleted": True, "updated_at": now}}
    )

    conv_id = msg["conversation_id"]
    room = await db.chat_rooms.find_one({"_id": ObjectId(conv_id)})
    participants = room["participants"] if room else [current_user["id"]]

    response_msg = ChatMessageResponse(
        id=message_id,
        conversation_id=conv_id,
        sender_id=msg["sender_id"],
        sender_username=msg.get("sender_username", ""),
        sender_full_name=msg.get("sender_full_name", ""),
        sender_avatar=msg.get("sender_avatar"),
        text=deleted_text,
        media_url=None,
        media_type="text",
        created_at=msg["created_at"],
        updated_at=now,
        is_edited=msg.get("is_edited", False),
        is_deleted=True,
        is_pinned=False,
        delivery_status=msg.get("delivery_status", "sent"),
        delivered_to=msg.get("delivered_to", []),
        read_by=msg.get("read_by", []),
        reactions={}
    )

    await chat_manager.broadcast_to_users(
        participants,
        {"event": "message_deleted", "conversation_id": conv_id, "message": response_msg.model_dump(mode="json")}
    )
    return response_msg

@router.post("/messages/{message_id}/react", status_code=status.HTTP_200_OK)
async def react_to_msg(
    message_id: str,
    payload: MessageReactionPayload,
    current_user: dict = Depends(get_current_user)
):
    try:
        return await connect_service.react_to_message(current_user, message_id, payload.emoji)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.post("/conversations/{conversation_id}/messages/{message_id}/pin", status_code=status.HTTP_200_OK)
async def pin_message(
    conversation_id: str,
    message_id: str,
    current_user: dict = Depends(get_current_user)
):
    try:
        return await connect_service.toggle_pin_message(current_user, conversation_id, message_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.post("/conversations/{conversation_id}/read", status_code=status.HTTP_200_OK)
async def mark_conversation_read(
    conversation_id: str,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    current_uid = current_user["id"]
    room = await db.chat_rooms.find_one({"_id": ObjectId(conversation_id), "participants": current_uid})
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    await db.chat_rooms.update_one(
        {"_id": ObjectId(conversation_id)},
        {"$set": {f"unread_counts.{current_uid}": 0}}
    )
    await db.chat_messages.update_many(
        {"conversation_id": conversation_id, "read_by": {"$ne": current_uid}},
        {"$addToSet": {"read_by": current_uid}, "$set": {"delivery_status": "read"}}
    )

    await chat_manager.broadcast_to_users(
        room["participants"],
        {"event": "conversation_read", "conversation_id": conversation_id, "read_by_user_id": current_uid}
    )
    return {"status": "ok", "conversation_id": conversation_id}

@router.get("/unread-count")
async def get_total_unread_count(current_user: dict = Depends(get_current_user)):
    db = get_database()
    if db is None:
        return {"unread_count": 0}

    current_uid = current_user["id"]
    cursor = db.chat_rooms.find({"participants": current_uid})
    total_unread = 0
    async for room in cursor:
        total_unread += room.get("unread_counts", {}).get(current_uid, 0)
    return {"unread_count": total_unread}

# -------------------------------------------------------------
# 4. Locked & Archived Chats
# -------------------------------------------------------------

@router.post("/conversations/{conversation_id}/lock", status_code=status.HTTP_200_OK)
async def lock_chat(
    conversation_id: str,
    payload: LockChatPayload,
    current_user: dict = Depends(get_current_user)
):
    try:
        return await connect_service.lock_conversation(current_user, conversation_id, payload.pin)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.post("/conversations/{conversation_id}/unlock", status_code=status.HTTP_200_OK)
async def unlock_chat(
    conversation_id: str,
    payload: UnlockChatPayload,
    current_user: dict = Depends(get_current_user)
):
    try:
        return await connect_service.unlock_conversation(current_user, conversation_id, payload.pin)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.post("/conversations/{conversation_id}/archive", status_code=status.HTTP_200_OK)
async def archive_chat(conversation_id: str, current_user: dict = Depends(get_current_user)):
    try:
        return await connect_service.toggle_archive_conversation(current_user, conversation_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

# -------------------------------------------------------------
# 5. Status Updates (24-Hour Expiration)
# -------------------------------------------------------------

@router.post("/status", response_model=ConnectStatusResponse, status_code=status.HTTP_201_CREATED)
async def create_status(
    payload: ConnectStatusCreatePayload,
    current_user: dict = Depends(get_current_user)
):
    doc = await connect_service.post_connect_status(
        current_user=current_user,
        media_url=payload.media_url,
        media_type=payload.media_type,
        caption=payload.caption,
        bg_color=payload.bg_color,
        font_style=payload.font_style,
        privacy=payload.privacy
    )
    return ConnectStatusResponse(
        id=str(doc["_id"]),
        user_id=doc["user_id"],
        user_username=doc["user_username"],
        user_full_name=doc["user_full_name"],
        user_avatar=doc.get("user_avatar"),
        media_url=doc.get("media_url"),
        media_type=doc.get("media_type", "text"),
        caption=doc.get("caption"),
        bg_color=doc.get("bg_color"),
        font_style=doc.get("font_style"),
        privacy=doc.get("privacy", "contacts"),
        viewers_count=len(doc.get("viewers", [])),
        created_at=doc["created_at"],
        expires_at=doc["expires_at"],
        has_viewed=False
    )

@router.get("/status/feed", response_model=List[ConnectStatusResponse])
async def list_statuses(current_user: dict = Depends(get_current_user)):
    statuses = await connect_service.get_connect_status_feed(current_user)
    current_uid = current_user["id"]
    return [
        ConnectStatusResponse(
            id=str(s["_id"]),
            user_id=s["user_id"],
            user_username=s["user_username"],
            user_full_name=s["user_full_name"],
            user_avatar=s.get("user_avatar"),
            media_url=s.get("media_url"),
            media_type=s.get("media_type", "text"),
            caption=s.get("caption"),
            bg_color=s.get("bg_color"),
            font_style=s.get("font_style"),
            privacy=s.get("privacy", "contacts"),
            viewers_count=len(s.get("viewers", [])),
            created_at=s["created_at"],
            expires_at=s["expires_at"],
            has_viewed=current_uid in s.get("viewers", [])
        )
        for s in statuses
    ]

@router.post("/status/{status_id}/view", status_code=status.HTTP_200_OK)
async def view_status(status_id: str, current_user: dict = Depends(get_current_user)):
    return await connect_service.record_status_view(current_user, status_id)

# -------------------------------------------------------------
# 6. Communities
# -------------------------------------------------------------

@router.post("/communities", response_model=CommunityResponse, status_code=status.HTTP_201_CREATED)
async def create_community_route(
    payload: CommunityCreatePayload,
    current_user: dict = Depends(get_current_user)
):
    comm = await connect_service.create_community(
        current_user=current_user,
        name=payload.name,
        description=payload.description,
        picture_url=payload.picture_url,
        group_ids=payload.group_ids
    )
    return CommunityResponse(
        id=str(comm["_id"]),
        name=comm["name"],
        description=comm.get("description"),
        picture_url=comm.get("picture_url"),
        creator_id=comm["creator_id"],
        admin_ids=comm["admin_ids"],
        group_ids=comm["group_ids"],
        announcement_group_id=comm.get("announcement_group_id"),
        created_at=comm["created_at"],
        updated_at=comm["updated_at"]
    )

@router.get("/communities", response_model=List[CommunityResponse])
async def list_communities(current_user: dict = Depends(get_current_user)):
    db = get_database()
    current_uid = current_user["id"]
    cursor = db.connect_communities.find({"admin_ids": current_uid}).sort("updated_at", -1)
    results = []
    async for c in cursor:
        results.append(CommunityResponse(
            id=str(c["_id"]),
            name=c["name"],
            description=c.get("description"),
            picture_url=c.get("picture_url"),
            creator_id=c["creator_id"],
            admin_ids=c["admin_ids"],
            group_ids=c["group_ids"],
            announcement_group_id=c.get("announcement_group_id"),
            created_at=c["created_at"],
            updated_at=c["updated_at"]
        ))
    return results

# -------------------------------------------------------------
# 7. WebRTC Voice & Video Call Signaling & History
# -------------------------------------------------------------

@router.post("/calls/initiate", response_model=CallHistoryResponse, status_code=status.HTTP_201_CREATED)
async def start_call(payload: CallInitiatePayload, current_user: dict = Depends(get_current_user)):
    try:
        call = await connect_service.initiate_call(
            current_user=current_user,
            conversation_id=payload.conversation_id,
            call_type=payload.call_type,
            recipient_id=payload.recipient_id
        )
        return CallHistoryResponse(
            id=str(call["_id"]),
            conversation_id=call["conversation_id"],
            caller_id=call["caller_id"],
            caller_name=call["caller_name"],
            caller_avatar=call.get("caller_avatar"),
            participants=call["participants"],
            call_type=call["call_type"],
            status=call["status"],
            duration_seconds=call["duration_seconds"],
            created_at=call["created_at"],
            ended_at=call.get("ended_at")
        )
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.post("/calls/signal", status_code=status.HTTP_200_OK)
async def call_signal(payload: CallSignalPayload, current_user: dict = Depends(get_current_user)):
    try:
        return await connect_service.handle_call_signal(
            current_user=current_user,
            call_id=payload.call_id,
            signal_type=payload.signal_type,
            payload=payload.payload
        )
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.get("/calls/history", response_model=List[CallHistoryResponse])
async def get_call_history(current_user: dict = Depends(get_current_user)):
    db = get_database()
    current_uid = current_user["id"]
    cursor = db.connect_calls.find({"participants": current_uid}).sort("created_at", -1).limit(50)
    history = []
    async for c in cursor:
        history.append(CallHistoryResponse(
            id=str(c["_id"]),
            conversation_id=c["conversation_id"],
            caller_id=c["caller_id"],
            caller_name=c["caller_name"],
            caller_avatar=c.get("caller_avatar"),
            participants=c["participants"],
            call_type=c["call_type"],
            status=c["status"],
            duration_seconds=c.get("duration_seconds", 0),
            created_at=c["created_at"],
            ended_at=c.get("ended_at")
        ))
    return history

# -------------------------------------------------------------
# 8. E2EE Signal Prekey Bundles
# -------------------------------------------------------------

@router.post("/e2ee/prekeys", status_code=status.HTTP_200_OK)
async def publish_prekeys(payload: E2EEPrekeyBundlePayload, current_user: dict = Depends(get_current_user)):
    return await connect_service.publish_e2ee_prekey_bundle(
        current_user=current_user,
        identity_key_pub=payload.identity_key_pub,
        signed_prekey_pub=payload.signed_prekey_pub,
        signed_prekey_sig=payload.signed_prekey_sig,
        one_time_prekeys=payload.one_time_prekeys
    )

@router.get("/e2ee/prekeys/{user_id}", response_model=E2EEPrekeyBundleResponse)
async def get_user_prekeys(user_id: str, device_id: Optional[str] = Query(None)):
    try:
        return await connect_service.fetch_e2ee_prekey_bundle(user_id, device_id)
    except LookupError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

# -------------------------------------------------------------
# 9. Real-time WebSocket Gateway
# -------------------------------------------------------------

@router.websocket("/ws")
async def chat_websocket_endpoint(websocket: WebSocket, token: Optional[str] = Query(None)):
    if not token:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    payload = decode_token(token)
    if not payload or payload.get("type") != "access":
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    user_id = payload.get("sub")
    if not user_id:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await chat_manager.connect(user_id, websocket)
    try:
        while True:
            data_text = await websocket.receive_text()
            if data_text == "ping":
                await websocket.send_text("pong")
            else:
                try:
                    import json
                    msg_json = json.loads(data_text)
                    if msg_json.get("type") == "typing":
                        conv_id = msg_json.get("conversation_id")
                        db = get_database()
                        room = await db.chat_rooms.find_one({"_id": ObjectId(conv_id)})
                        if room:
                            targets = [p for p in room["participants"] if p != user_id]
                            await chat_manager.broadcast_to_users(
                                targets,
                                {"event": "user_typing", "conversation_id": conv_id, "user_id": user_id}
                            )
                except Exception:
                    pass
    except WebSocketDisconnect:
        chat_manager.disconnect(user_id, websocket)
    except Exception:
        chat_manager.disconnect(user_id, websocket)
