from fastapi import APIRouter, HTTPException, status, Depends, Query, WebSocket, WebSocketDisconnect
from datetime import datetime, timezone
from typing import List, Optional
from bson import ObjectId
import html

from app.schemas.all_schemas import (
    UserPublicSummary,
    ChatConversationCreate,
    ChatConversationResponse,
    ChatMessageCreate,
    ChatMessageUpdate,
    ChatMessageResponse,
    LastMessageSummary
)
from app.api.deps import get_current_user
from app.database.client import get_database
from app.core.rate_limit import check_chat_user_rate_limit
from app.core.ws_manager import chat_manager
from app.core.security import decode_token

router = APIRouter(prefix="/chat", tags=["User Messaging"])

def sanitize_text(text: str) -> str:
    """Escapes HTML entities in text to prevent XSS."""
    return html.escape(text.strip())

# 1. Search Users (Public discovery for direct messaging)
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
            username=u["username"],
            full_name=u["full_name"],
            avatar_url=u.get("avatar_url")
        ))
    return results

# 2. Get or Create 1-to-1 Conversation
@router.post("/conversations", response_model=ChatConversationResponse, status_code=status.HTTP_200_OK)
async def get_or_create_conversation(
    req: ChatConversationCreate,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    current_uid = current_user["id"]
    recipient_uid = req.recipient_id.strip()

    if current_uid == recipient_uid:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot create conversation with yourself")

    try:
        recip_obj = ObjectId(recipient_uid)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid recipient ID")

    recipient_user = await db.users.find_one({"_id": recip_obj})
    if not recipient_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recipient user not found")

    # Check if a 1-to-1 room already exists between these 2 participants
    existing_room = await db.chat_rooms.find_one({
        "type": "direct",
        "participants": {"$all": [current_uid, recipient_uid], "$size": 2}
    })

    if existing_room:
        unread_for_user = existing_room.get("unread_counts", {}).get(current_uid, 0)
        return ChatConversationResponse(
            id=str(existing_room["_id"]),
            type=existing_room.get("type", "direct"),
            participants=existing_room["participants"],
            participant_meta=existing_room.get("participant_meta", {}),
            last_message=existing_room.get("last_message"),
            unread_count=unread_for_user,
            created_at=existing_room.get("created_at", datetime.now(timezone.utc)),
            updated_at=existing_room.get("updated_at", datetime.now(timezone.utc))
        )

    # Create new 1-to-1 room
    now = datetime.now(timezone.utc)
    participant_meta = {
        current_uid: {
            "id": current_uid,
            "username": current_user["username"],
            "full_name": current_user["full_name"],
            "avatar_url": current_user.get("avatar_url")
        },
        recipient_uid: {
            "id": recipient_uid,
            "username": recipient_user["username"],
            "full_name": recipient_user["full_name"],
            "avatar_url": recipient_user.get("avatar_url")
        }
    }

    room_doc = {
        "type": "direct",
        "participants": [current_uid, recipient_uid],
        "participant_meta": participant_meta,
        "last_message": None,
        "unread_counts": {current_uid: 0, recipient_uid: 0},
        "created_at": now,
        "updated_at": now
    }

    insert_res = await db.chat_rooms.insert_one(room_doc)
    room_id = str(insert_res.inserted_id)

    return ChatConversationResponse(
        id=room_id,
        type="direct",
        participants=[current_uid, recipient_uid],
        participant_meta=participant_meta,
        last_message=None,
        unread_count=0,
        created_at=now,
        updated_at=now
    )

# 3. List Conversations for Current User
@router.get("/conversations", response_model=List[ChatConversationResponse])
async def list_conversations(
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        return []

    current_uid = current_user["id"]
    cursor = db.chat_rooms.find({"participants": current_uid}).sort("updated_at", -1).limit(limit)

    results = []
    async for room in cursor:
        unread_for_user = room.get("unread_counts", {}).get(current_uid, 0)
        results.append(ChatConversationResponse(
            id=str(room["_id"]),
            type=room.get("type", "direct"),
            participants=room["participants"],
            participant_meta=room.get("participant_meta", {}),
            last_message=room.get("last_message"),
            unread_count=unread_for_user,
            created_at=room.get("created_at", datetime.now(timezone.utc)),
            updated_at=room.get("updated_at", datetime.now(timezone.utc))
        ))
    return results

# 4. Get Paginated Message History for a Conversation
@router.get("/conversations/{conversation_id}/messages", response_model=List[ChatMessageResponse])
async def get_conversation_messages(
    conversation_id: str,
    limit: int = Query(40, ge=1, le=100),
    before: Optional[str] = Query(None, description="ISO timestamp cursor for messages before this date"),
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    try:
        room_obj = ObjectId(conversation_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid conversation ID")

    # Authorize: user must be participant
    room = await db.chat_rooms.find_one({"_id": room_obj, "participants": current_user["id"]})
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found or unauthorized")

    query: dict = {"conversation_id": conversation_id}
    if before:
        try:
            cursor_dt = datetime.fromisoformat(before)
            query["created_at"] = {"$lt": cursor_dt}
        except Exception:
            pass

    # Retrieve messages ordered by created_at ascending
    cursor = db.chat_messages.find(query).sort("created_at", -1).limit(limit)
    messages = []
    async for msg in cursor:
        messages.append(ChatMessageResponse(
            id=str(msg["_id"]),
            conversation_id=msg["conversation_id"],
            sender_id=msg["sender_id"],
            sender_username=msg.get("sender_username", ""),
            sender_full_name=msg.get("sender_full_name", ""),
            sender_avatar=msg.get("sender_avatar"),
            text=msg.get("text", ""),
            created_at=msg["created_at"],
            updated_at=msg.get("updated_at", msg["created_at"]),
            is_edited=msg.get("is_edited", False),
            is_deleted=msg.get("is_deleted", False),
            read_by=msg.get("read_by", [])
        ))

    # Return in chronological order
    messages.reverse()
    return messages

# 5. Send a Message
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
        room_obj = ObjectId(conversation_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid conversation ID")

    # Authorize participant
    room = await db.chat_rooms.find_one({"_id": room_obj, "participants": current_uid})
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found or unauthorized")

    clean_text = sanitize_text(msg_in.text)
    if not clean_text:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Message cannot be blank")

    now = datetime.now(timezone.utc)
    msg_doc = {
        "conversation_id": conversation_id,
        "sender_id": current_uid,
        "sender_username": current_user["username"],
        "sender_full_name": current_user["full_name"],
        "sender_avatar": current_user.get("avatar_url"),
        "text": clean_text,
        "created_at": now,
        "updated_at": now,
        "is_edited": False,
        "is_deleted": False,
        "read_by": [current_uid]
    }

    insert_res = await db.chat_messages.insert_one(msg_doc)
    msg_id = str(insert_res.inserted_id)

    # Update conversation's last_message and unread counts for other participants
    last_msg = {
        "id": msg_id,
        "sender_id": current_uid,
        "text": clean_text[:120],
        "created_at": now
    }

    update_fields: dict = {
        "last_message": last_msg,
        "updated_at": now
    }
    inc_fields: dict = {}
    for p in room["participants"]:
        if p != current_uid:
            inc_fields[f"unread_counts.{p}"] = 1

    update_op: dict = {"$set": update_fields}
    if inc_fields:
        update_op["$inc"] = inc_fields

    await db.chat_rooms.update_one({"_id": room_obj}, update_op)

    # Trigger Phase 4K notification for each other participant
    from app.services.notification_service import create_event_notification
    for p in room["participants"]:
        if p != current_uid:
            await create_event_notification(
                recipient_user_id=p,
                actor_user_id=current_uid,
                category="chat",
                event_type="chat_message",
                title=f"New message from {current_user['full_name']}",
                desc=clean_text[:100] + ("..." if len(clean_text) > 100 else ""),
                navigation_target=f"chat:{conversation_id}",
                metadata={"conversation_id": conversation_id, "message_id": msg_id, "sender_username": current_user["username"]},
                event_id=f"chat_msg_{msg_id}_{p}"
            )

    response_msg = ChatMessageResponse(
        id=msg_id,
        conversation_id=conversation_id,
        sender_id=current_uid,
        sender_username=current_user["username"],
        sender_full_name=current_user["full_name"],
        sender_avatar=current_user.get("avatar_url"),
        text=clean_text,
        created_at=now,
        updated_at=now,
        is_edited=False,
        is_deleted=False,
        read_by=[current_uid]
    )

    # Real-time WebSocket delivery to all participants
    await chat_manager.broadcast_to_users(
        room["participants"],
        {
            "event": "new_message",
            "conversation_id": conversation_id,
            "message": response_msg.model_dump(mode="json")
        }
    )

    return response_msg

# 6. Edit a Message
@router.patch("/messages/{message_id}", response_model=ChatMessageResponse)
async def edit_message(
    message_id: str,
    update_in: ChatMessageUpdate,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    try:
        msg_obj = ObjectId(message_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid message ID")

    msg = await db.chat_messages.find_one({"_id": msg_obj})
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    # Authorize: only the original sender can edit their own message
    if msg["sender_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot edit another user's message")

    if msg.get("is_deleted", False):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot edit a deleted message")

    clean_text = sanitize_text(update_in.text)
    now = datetime.now(timezone.utc)

    await db.chat_messages.update_one(
        {"_id": msg_obj},
        {"$set": {"text": clean_text, "is_edited": True, "updated_at": now}}
    )

    room = await db.chat_rooms.find_one({"_id": ObjectId(msg["conversation_id"])})
    participants = room["participants"] if room else [current_user["id"]]

    response_msg = ChatMessageResponse(
        id=message_id,
        conversation_id=msg["conversation_id"],
        sender_id=msg["sender_id"],
        sender_username=msg.get("sender_username", ""),
        sender_full_name=msg.get("sender_full_name", ""),
        sender_avatar=msg.get("sender_avatar"),
        text=clean_text,
        created_at=msg["created_at"],
        updated_at=now,
        is_edited=True,
        is_deleted=False,
        read_by=msg.get("read_by", [])
    )

    await chat_manager.broadcast_to_users(
        participants,
        {
            "event": "message_edited",
            "conversation_id": msg["conversation_id"],
            "message": response_msg.model_dump(mode="json")
        }
    )

    return response_msg

# 7. Delete a Message (Soft delete)
@router.delete("/messages/{message_id}", response_model=ChatMessageResponse)
async def delete_message(
    message_id: str,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    try:
        msg_obj = ObjectId(message_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid message ID")

    msg = await db.chat_messages.find_one({"_id": msg_obj})
    if not msg:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Message not found")

    if msg["sender_id"] != current_user["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot delete another user's message")

    now = datetime.now(timezone.utc)
    deleted_text = "This message was deleted."
    await db.chat_messages.update_one(
        {"_id": msg_obj},
        {"$set": {"text": deleted_text, "is_deleted": True, "updated_at": now}}
    )

    room = await db.chat_rooms.find_one({"_id": ObjectId(msg["conversation_id"])})
    participants = room["participants"] if room else [current_user["id"]]

    response_msg = ChatMessageResponse(
        id=message_id,
        conversation_id=msg["conversation_id"],
        sender_id=msg["sender_id"],
        sender_username=msg.get("sender_username", ""),
        sender_full_name=msg.get("sender_full_name", ""),
        sender_avatar=msg.get("sender_avatar"),
        text=deleted_text,
        created_at=msg["created_at"],
        updated_at=now,
        is_edited=msg.get("is_edited", False),
        is_deleted=True,
        read_by=msg.get("read_by", [])
    )

    await chat_manager.broadcast_to_users(
        participants,
        {
            "event": "message_deleted",
            "conversation_id": msg["conversation_id"],
            "message": response_msg.model_dump(mode="json")
        }
    )

    return response_msg

# 8. Mark Conversation as Read
@router.post("/conversations/{conversation_id}/read", status_code=status.HTTP_200_OK)
async def mark_conversation_read(
    conversation_id: str,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    current_uid = current_user["id"]
    try:
        room_obj = ObjectId(conversation_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid conversation ID")

    room = await db.chat_rooms.find_one({"_id": room_obj, "participants": current_uid})
    if not room:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found or unauthorized")

    # Reset unread count for current user
    await db.chat_rooms.update_one(
        {"_id": room_obj},
        {"$set": {f"unread_counts.{current_uid}": 0}}
    )

    # Add current user to read_by in unread messages
    await db.chat_messages.update_many(
        {"conversation_id": conversation_id, "read_by": {"$ne": current_uid}},
        {"$addToSet": {"read_by": current_uid}}
    )

    # Notify other participants that messages were read
    await chat_manager.broadcast_to_users(
        room["participants"],
        {
            "event": "conversation_read",
            "conversation_id": conversation_id,
            "read_by_user_id": current_uid
        }
    )

    return {"status": "ok", "conversation_id": conversation_id}

# 9. Total Unread Message Count for User
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

# 10. Real-time WebSocket Endpoint
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
            # Client can send ping/pong or heartbeats
            if data_text == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        chat_manager.disconnect(user_id, websocket)
    except Exception:
        chat_manager.disconnect(user_id, websocket)
