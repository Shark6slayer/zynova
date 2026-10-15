from fastapi import APIRouter, HTTPException, status, Depends, Query
from datetime import datetime, timezone
from typing import List
from bson import ObjectId
from app.schemas.all_schemas import ConversationCreate, ConversationResponse, MessageItem
from app.api.deps import get_current_user
from app.database.client import get_database

router = APIRouter(prefix="/conversations", tags=["Conversations"])

@router.get("", response_model=List[ConversationResponse])
async def list_conversations(
    limit: int = Query(20, ge=1, le=100),
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        return []

    cursor = db.conversations.find({"user_id": current_user["id"]}).sort("updated_at", -1).limit(limit)
    conversations = []
    async for doc in cursor:
        conversations.append(ConversationResponse(
            id=str(doc["_id"]),
            user_id=doc["user_id"],
            title=doc.get("title", "New Conversation"),
            model=doc.get("model", "SUPER Multilingual (Indic-v2)"),
            created_at=doc.get("created_at", datetime.now(timezone.utc)),
            updated_at=doc.get("updated_at", datetime.now(timezone.utc)),
            messages=doc.get("messages", [])
        ))
    return conversations

@router.post("", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
async def create_conversation(
    conv_in: ConversationCreate,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    now = datetime.now(timezone.utc)
    conv_doc = {
        "user_id": current_user["id"],
        "title": conv_in.title,
        "model": conv_in.model,
        "created_at": now,
        "updated_at": now,
        "messages": [
            {
                "id": "init_1",
                "sender": "assistant",
                "text": "Namaste! I am SUPER_AI Copilot. How may I assist your day?",
                "timestamp": "10:00 AM"
            }
        ]
    }

    res = await db.conversations.insert_one(conv_doc)
    return ConversationResponse(
        id=str(res.inserted_id),
        user_id=conv_doc["user_id"],
        title=conv_doc["title"],
        model=conv_doc["model"],
        created_at=conv_doc["created_at"],
        updated_at=conv_doc["updated_at"],
        messages=conv_doc["messages"]
    )

@router.get("/{conversation_id}", response_model=ConversationResponse)
async def get_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    try:
        obj_id = ObjectId(conversation_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid conversation ID")

    doc = await db.conversations.find_one({"_id": obj_id, "user_id": current_user["id"]})
    if not doc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found or unauthorized")

    return ConversationResponse(
        id=str(doc["_id"]),
        user_id=doc["user_id"],
        title=doc.get("title", "Conversation"),
        model=doc.get("model", "SUPER Multilingual (Indic-v2)"),
        created_at=doc.get("created_at", datetime.now(timezone.utc)),
        updated_at=doc.get("updated_at", datetime.now(timezone.utc)),
        messages=doc.get("messages", [])
    )

@router.delete("/{conversation_id}", status_code=status.HTTP_200_OK)
async def delete_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user)
):
    db = get_database()
    if db is None:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Database unavailable")

    try:
        obj_id = ObjectId(conversation_id)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid conversation ID")

    result = await db.conversations.delete_one({"_id": obj_id, "user_id": current_user["id"]})
    if result.deleted_count == 0:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found or unauthorized")

    return {"status": "deleted", "conversation_id": conversation_id}
