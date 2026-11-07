import json
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.services.ai_engine_service import ai_engine_service
from app.core.audit_ledger import record_audit_event

logger = logging.getLogger("zynova.ai_api")
router = APIRouter(prefix="/ai", tags=["ai"])

class AIChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    prompt: str = Field(..., min_length=1, max_length=10000, description="User input message")
    provider: Optional[str] = Field(None, description="Requested provider: gemini, openai, anthropic, mock")
    model: Optional[str] = Field(None, description="Specific model ID")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0)
    locale: Optional[str] = Field("en", description="Target Indic language code")

class ConversationResponse(BaseModel):
    id: str
    title: str
    message_count: int
    updated_at: str
    last_message: Optional[str] = None

@router.get("/models")
async def get_available_models():
    """Lists all supported AI providers and their configuration status."""
    return {
        "status": "success",
        "models": ai_engine_service.list_available_models()
    }

@router.get("/conversations")
async def list_conversations(
    limit: int = Query(20, ge=1, le=50),
    current_user: dict = Depends(get_current_user)
):
    """Retrieves all conversation threads belonging to the authenticated user."""
    user_id = str(current_user["_id"])
    convs = await ai_engine_service.list_user_conversations(user_id=user_id, limit=limit)
    formatted = []
    for c in convs:
        last_msg = c.get("messages", [{}])[0].get("content", "") if c.get("messages") else None
        formatted.append({
            "id": c["id"],
            "title": c.get("title", "Conversation"),
            "message_count": c.get("message_count", 0),
            "updated_at": c["updated_at"].isoformat() if hasattr(c["updated_at"], "isoformat") else str(c["updated_at"]),
            "last_message": last_msg[:60] + "..." if last_msg and len(last_msg) > 60 else last_msg
        })
    return {"status": "success", "conversations": formatted}

@router.get("/conversations/{conversation_id}")
async def get_conversation_details(
    conversation_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Loads complete message history of a specific conversation thread."""
    user_id = str(current_user["_id"])
    conv = await ai_engine_service.get_conversation_by_id(user_id=user_id, conversation_id=conversation_id)
    if not conv:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")

    messages = conv.get("messages", [])
    # Format datetimes
    formatted_msgs = []
    for m in messages:
        dt = m.get("created_at")
        formatted_msgs.append({
            "id": m.get("id"),
            "role": m.get("role"),
            "content": m.get("content"),
            "model_used": m.get("model_used"),
            "created_at": dt.isoformat() if hasattr(dt, "isoformat") else str(dt)
        })

    return {
        "status": "success",
        "conversation": {
            "id": conv["id"],
            "title": conv.get("title", "Conversation"),
            "messages": formatted_msgs
        }
    }

@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: str,
    current_user: dict = Depends(get_current_user)
):
    """Deletes a conversation thread and its associated message history."""
    user_id = str(current_user["_id"])
    success = await ai_engine_service.delete_conversation(user_id=user_id, conversation_id=conversation_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Conversation not found")
    return {"status": "success", "message": "Conversation deleted"}

@router.post("/chat/stream")
async def stream_chat(
    req: AIChatRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    Primary real-time AI inference endpoint using Server-Sent Events (SSE).
    Streams chunks token-by-token and persists conversation history in MongoDB.
    """
    user_id = str(current_user["_id"])
    user_name = current_user.get("full_name") or current_user.get("username", "User")

    # 1. Load or create conversation thread
    first_title = req.prompt[:30].strip() + ("..." if len(req.prompt) > 30 else "")
    conv = await ai_engine_service.get_or_create_conversation(
        user_id=user_id,
        conversation_id=req.conversation_id,
        title=first_title
    )
    conv_id = conv["id"]

    # 2. Persist user message
    await ai_engine_service.append_message(
        user_id=user_id,
        conversation_id=conv_id,
        role="user",
        content=req.prompt
    )

    # 3. Assemble context window & system instructions
    history = conv.get("messages", []) + [{"role": "user", "content": req.prompt}]
    context = await ai_engine_service.prune_context_window(history, max_messages=10)
    system_instruction = ai_engine_service.build_system_instruction(
        user_locale=req.locale or "en",
        user_name=user_name
    )

    # 4. Resolve provider and model
    provider_id = req.provider or "mock"
    provider = ai_engine_service.get_provider(provider_id)
    model = req.model or (provider.get_supported_models()[0]["id"] if provider.get_supported_models() else "default")

    # 5. Log audit ledger event
    try:
        await record_audit_event(
            event_type="AI_INFERENCE_INVOKED",
            raw_actor_id=user_id,
            metadata={
                "provider": provider.provider_id,
                "model": model,
                "prompt_length": len(req.prompt),
                "locale": req.locale,
                "conversation_id": conv_id
            }
        )
    except Exception as e:
        logger.warning(f"Failed to record audit event for AI inference: {e}")

    # 6. Stream generator
    async def event_generator():
        yield f"data: {json.dumps({'type': 'start', 'conversation_id': conv_id, 'model': model, 'provider': provider.provider_id})}\n\n"
        full_response_acc = []

        try:
            async for token in provider.stream_chat(
                messages=context,
                model=model,
                temperature=req.temperature or 0.7,
                system_instruction=system_instruction
            ):
                full_response_acc.append(token)
                yield f"data: {json.dumps({'type': 'chunk', 'text': token})}\n\n"

            full_text = "".join(full_response_acc)
            # 7. Persist assistant completion to MongoDB
            await ai_engine_service.append_message(
                user_id=user_id,
                conversation_id=conv_id,
                role="assistant",
                content=full_text,
                model_used=model
            )
            yield f"data: {json.dumps({'type': 'done', 'full_length': len(full_text)})}\n\n"

        except Exception as e:
            logger.error(f"Error during AI streaming: {e}")
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
