"""
routes/social_chat.py - ZenoSocial Zen_ID Direct Messaging & Content Sharing
Strictly separated from ZENOVA Connect (Phone-based /chat/*).

Rules:
- Identity: Zen_ID (username)
- Follower relationships determine messaging permissions:
  * Mutual-follow: Unlimited messaging.
  * Non-mutual-follow: Max 3 messages until recipient follows sender back.
- Sharing Reels & Posts with original creator attribution.
- Database Collections: social_conversations, social_messages (isolated from Connect).
"""

from fastapi import APIRouter, HTTPException, status, Depends, Query
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from bson import ObjectId
import html

from app.schemas.all_schemas import (
    SocialMessageSendPayload,
    SocialContentSharePayload,
    SocialMessageResponse,
    SocialConversationResponse,
    UserPublicSummary
)
from app.api.deps import get_current_user
from app.database.client import get_database
from app.core.rate_limit import check_chat_user_rate_limit
from app.core.audit_ledger import record_audit_event

router = APIRouter(prefix="/social/messages", tags=["ZenoSocial Messaging"])

NON_MUTUAL_MAX_MESSAGES = 3

def sanitize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    return html.escape(text.strip())

async def check_mutual_follow(db, user_a_id: str, user_b_id: str) -> bool:
    """Checks if user_a and user_b mutually follow each other."""
    a_follows_b = await db.followers.find_one({"follower_id": user_a_id, "following_id": user_b_id})
    b_follows_a = await db.followers.find_one({"follower_id": user_b_id, "following_id": user_a_id})
    return bool(a_follows_b and b_follows_a)

async def count_accepted_messages(db, sender_id: str, recipient_id: str) -> int:
    """Counts accepted messages sent from sender to recipient in non-mutual relationships."""
    count = await db.social_messages.count_documents({
        "sender_id": sender_id,
        "recipient_id": recipient_id,
        "status": {"$in": ["sent", "delivered", "read"]}
    })
    return count

@router.get("/conversations", response_model=List[SocialConversationResponse])
async def list_social_conversations(
    limit: int = Query(20, ge=1, le=50),
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        return []

    user_id = current_user["id"]
    cursor = db.social_conversations.find({
        "participant_ids": user_id
    }).sort("updated_at", -1).limit(limit)

    results = []
    async for conv in cursor:
        other_id = [pid for pid in conv["participant_ids"] if pid != user_id][0] if len(conv["participant_ids"]) > 1 else user_id
        other_user = await db.users.find_one({"_id": ObjectId(other_id)})
        other_summary = UserPublicSummary(
            id=other_id,
            username=other_user.get("username", "user") if other_user else "user",
            full_name=other_user.get("full_name", "Zeno User") if other_user else "Zeno User",
            avatar_url=other_user.get("avatar_url") if other_user else None,
            is_verified=other_user.get("is_verified", False) if other_user else False
        )

        is_mutual = await check_mutual_follow(db, user_id, other_id)
        sent_count = await count_accepted_messages(db, user_id, other_id)
        
        remaining = 999999 if is_mutual else max(0, NON_MUTUAL_MAX_MESSAGES - sent_count)
        can_send = is_mutual or (sent_count < NON_MUTUAL_MAX_MESSAGES)

        # Count unread messages for current user
        unread = await db.social_messages.count_documents({
            "conversation_id": str(conv["_id"]),
            "recipient_id": user_id,
            "status": {"$ne": "read"}
        })

        results.append(SocialConversationResponse(
            id=str(conv["_id"]),
            participant_ids=conv["participant_ids"],
            participant_zen_ids=conv.get("participant_zen_ids", []),
            other_participant=other_summary,
            is_mutual_follow=is_mutual,
            messages_sent_by_me=sent_count,
            remaining_messages_allowed=remaining,
            can_send_message=can_send,
            last_message=conv.get("last_message"),
            unread_count=unread,
            updated_at=conv.get("updated_at", datetime.now(timezone.utc))
        ))

    return results

@router.post("/send", response_model=SocialMessageResponse, status_code=status.HTTP_201_CREATED, dependencies=[Depends(check_chat_user_rate_limit)])
async def send_social_message(
    payload: SocialMessageSendPayload,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    sender_id = current_user["id"]
    sender_zen_id = current_user.get("username", "")

    # Resolve recipient by Zen_ID (username)
    clean_target = payload.recipient_zen_id.lower().lstrip("@").strip()
    recipient = await db.users.find_one({"username": clean_target})
    if not recipient:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"User with Zen_ID '@{clean_target}' not found")

    recipient_id = str(recipient["_id"])
    if recipient_id == sender_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Cannot send social messages to yourself")

    # Check blocking
    blocked_by_me = await db.blocked_users.find_one({"user_id": sender_id, "blocked_user_id": recipient_id})
    blocked_by_them = await db.blocked_users.find_one({"user_id": recipient_id, "blocked_user_id": sender_id})
    if blocked_by_me or blocked_by_them:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Cannot send message: communication is restricted")

    # Follower & 3-Message Restriction Check
    is_mutual = await check_mutual_follow(db, sender_id, recipient_id)
    sent_count = await count_accepted_messages(db, sender_id, recipient_id)

    if not is_mutual and sent_count >= NON_MUTUAL_MAX_MESSAGES:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "NON_MUTUAL_LIMIT_REACHED",
                "message": f"Non-mutual messaging limit reached (3/3). Recipient @{clean_target} must follow you to unlock unlimited messaging.",
                "messages_sent": sent_count,
                "limit": NON_MUTUAL_MAX_MESSAGES
            }
        )

    # Find or create isolated social conversation
    conv = await db.social_conversations.find_one({
        "participant_ids": {"$all": [sender_id, recipient_id], "$size": 2}
    })

    now = datetime.now(timezone.utc)
    if not conv:
        conv_doc = {
            "participant_ids": [sender_id, recipient_id],
            "participant_zen_ids": [sender_zen_id, clean_target],
            "created_at": now,
            "updated_at": now,
            "last_message": None
        }
        res = await db.social_conversations.insert_one(conv_doc)
        conv_id = str(res.inserted_id)
    else:
        conv_id = str(conv["_id"])

    # Insert social message
    clean_text = sanitize_text(payload.text)
    msg_doc = {
        "conversation_id": conv_id,
        "sender_id": sender_id,
        "sender_zen_id": sender_zen_id,
        "recipient_id": recipient_id,
        "recipient_zen_id": clean_target,
        "text": clean_text,
        "shared_content": None,
        "status": "sent",
        "reply_to_message_id": payload.reply_to_message_id,
        "created_at": now
    }
    msg_res = await db.social_messages.insert_one(msg_doc)
    msg_id = str(msg_res.inserted_id)

    # Update conversation's last message
    last_msg = {
        "id": msg_id,
        "sender_id": sender_id,
        "sender_zen_id": sender_zen_id,
        "text": clean_text[:100],
        "created_at": now.isoformat()
    }
    await db.social_conversations.update_one(
        {"_id": ObjectId(conv_id)},
        {"$set": {"last_message": last_msg, "updated_at": now}}
    )

    return SocialMessageResponse(
        id=msg_id,
        conversation_id=conv_id,
        sender_id=sender_id,
        sender_zen_id=sender_zen_id,
        recipient_id=recipient_id,
        recipient_zen_id=clean_target,
        text=clean_text,
        shared_content=None,
        status="sent",
        created_at=now
    )

@router.post("/share-content", response_model=List[SocialMessageResponse], status_code=status.HTTP_201_CREATED, dependencies=[Depends(check_chat_user_rate_limit)])
async def share_social_content(
    payload: SocialContentSharePayload,
    current_user: dict = Depends(get_current_user)
):
    """Shares a Reel or Post with recipient Zen_IDs with original creator attribution."""
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    sender_id = current_user["id"]
    sender_zen_id = current_user.get("username", "")

    # Validate content existence and extract attribution
    shared_content_meta = None
    if payload.content_type == "post":
        post = await db.posts.find_one({"_id": ObjectId(payload.content_id)})
        if not post:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original post not found or has been removed")
        shared_content_meta = {
            "type": "post",
            "content_id": payload.content_id,
            "creator_id": post.get("author_id", ""),
            "creator_zen_id": post.get("author_username", "creator"),
            "caption_snippet": (post.get("content") or "")[:120],
            "media_url": post.get("media_url") or (post.get("media_urls", [None])[0] if post.get("media_urls") else None)
        }
    elif payload.content_type == "reel":
        reel = await db.videos.find_one({"_id": ObjectId(payload.content_id)})
        if not reel:
            # Check reels collection fallback
            reel = await db.reels.find_one({"_id": ObjectId(payload.content_id)})
        if not reel:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Original reel not found or has been removed")
        shared_content_meta = {
            "type": "reel",
            "content_id": payload.content_id,
            "creator_id": reel.get("owner_id", reel.get("author_id", "")),
            "creator_zen_id": reel.get("owner_username", reel.get("author_username", "creator")),
            "caption_snippet": (reel.get("caption", reel.get("title", "")))[:120],
            "thumbnail_url": reel.get("thumbnail_url", ""),
            "video_url": reel.get("video_url", "")
        }

    responses = []
    now = datetime.now(timezone.utc)

    for target_zen_id in payload.recipient_zen_ids:
        clean_target = target_zen_id.lower().lstrip("@").strip()
        recipient = await db.users.find_one({"username": clean_target})
        if not recipient:
            continue

        recipient_id = str(recipient["_id"])
        if recipient_id == sender_id:
            continue

        # Check blocking
        blocked = await db.blocked_users.find_one({
            "$or": [
                {"user_id": sender_id, "blocked_user_id": recipient_id},
                {"user_id": recipient_id, "blocked_user_id": sender_id}
            ]
        })
        if blocked:
            continue

        # Enforce 3-message rule if non-mutual
        is_mutual = await check_mutual_follow(db, sender_id, recipient_id)
        sent_count = await count_accepted_messages(db, sender_id, recipient_id)
        if not is_mutual and sent_count >= NON_MUTUAL_MAX_MESSAGES:
            continue # Skip sending if recipient has not followed back and limit reached

        # Conversation
        conv = await db.social_conversations.find_one({
            "participant_ids": {"$all": [sender_id, recipient_id], "$size": 2}
        })
        if not conv:
            conv_doc = {
                "participant_ids": [sender_id, recipient_id],
                "participant_zen_ids": [sender_zen_id, clean_target],
                "created_at": now,
                "updated_at": now,
                "last_message": None
            }
            res = await db.social_conversations.insert_one(conv_doc)
            conv_id = str(res.inserted_id)
        else:
            conv_id = str(conv["_id"])

        text_content = payload.message or f"Shared a {payload.content_type} by @{shared_content_meta.get('creator_zen_id')}"
        msg_doc = {
            "conversation_id": conv_id,
            "sender_id": sender_id,
            "sender_zen_id": sender_zen_id,
            "recipient_id": recipient_id,
            "recipient_zen_id": clean_target,
            "text": sanitize_text(text_content),
            "shared_content": shared_content_meta,
            "status": "sent",
            "created_at": now
        }
        msg_res = await db.social_messages.insert_one(msg_doc)
        msg_id = str(msg_res.inserted_id)

        await db.social_conversations.update_one(
            {"_id": ObjectId(conv_id)},
            {"$set": {
                "last_message": {
                    "id": msg_id,
                    "sender_id": sender_id,
                    "sender_zen_id": sender_zen_id,
                    "text": f"Shared {payload.content_type}",
                    "created_at": now.isoformat()
                },
                "updated_at": now
            }}
        )

        responses.append(SocialMessageResponse(
            id=msg_id,
            conversation_id=conv_id,
            sender_id=sender_id,
            sender_zen_id=sender_zen_id,
            recipient_id=recipient_id,
            recipient_zen_id=clean_target,
            text=text_content,
            shared_content=shared_content_meta,
            status="sent",
            created_at=now
        ))

    return responses

@router.get("/conversations/{conv_id}/messages")
async def get_social_messages(
    conv_id: str,
    limit: int = Query(50, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        return {"messages": [], "relationship_info": None}

    user_id = current_user["id"]
    conv = await db.social_conversations.find_one({"_id": ObjectId(conv_id), "participant_ids": user_id})
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Social conversation not found")

    other_id = [pid for pid in conv["participant_ids"] if pid != user_id][0] if len(conv["participant_ids"]) > 1 else user_id

    # Check mutual follow and calculate limits
    is_mutual = await check_mutual_follow(db, user_id, other_id)
    sent_count = await count_accepted_messages(db, user_id, other_id)
    remaining = 999999 if is_mutual else max(0, NON_MUTUAL_MAX_MESSAGES - sent_count)
    can_send = is_mutual or (sent_count < NON_MUTUAL_MAX_MESSAGES)

    cursor = db.social_messages.find({"conversation_id": conv_id}).sort("created_at", -1).limit(limit)
    messages = []
    async for m in cursor:
        messages.append({
            "id": str(m["_id"]),
            "conversation_id": m["conversation_id"],
            "sender_id": m["sender_id"],
            "sender_zen_id": m.get("sender_zen_id", ""),
            "recipient_id": m["recipient_id"],
            "recipient_zen_id": m.get("recipient_zen_id", ""),
            "text": m.get("text", ""),
            "shared_content": m.get("shared_content"),
            "status": m.get("status", "sent"),
            "created_at": m.get("created_at")
        })

    # Reverse to chronological order
    messages.reverse()

    # Mark unread incoming messages as read
    await db.social_messages.update_many(
        {"conversation_id": conv_id, "recipient_id": user_id, "status": {"$ne": "read"}},
        {"$set": {"status": "read"}}
    )

    return {
        "conversation_id": conv_id,
        "is_mutual_follow": is_mutual,
        "messages_sent_by_me": sent_count,
        "remaining_messages_allowed": remaining,
        "can_send_message": can_send,
        "non_mutual_limit": NON_MUTUAL_MAX_MESSAGES,
        "messages": messages
    }
