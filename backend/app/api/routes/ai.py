import json
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import get_current_user
from app.services.ai_engine_service import ai_engine_service
from app.core.ai_errors import AIErrorCode, AIProviderException
from app.core.audit_ledger import record_audit_event

logger = logging.getLogger("zynova.ai_api")
router = APIRouter(prefix="/ai", tags=["ai"])

class AIChatRequest(BaseModel):
    conversation_id: Optional[str] = None
    prompt: str = Field(..., min_length=1, max_length=10000, description="User input message")
    provider: Optional[str] = Field("gemini", description="Requested provider: gemini, openai, anthropic, mock")
    model: Optional[str] = Field(None, description="Specific model ID")
    temperature: Optional[float] = Field(0.7, ge=0.0, le=2.0)
    locale: Optional[str] = Field("en", description="Target Indic language code")

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
    formatted_msgs = []
    for m in messages:
        dt = m.get("created_at")
        formatted_msgs.append({
            "id": m.get("id"),
            "role": m.get("role"),
            "content": m.get("content"),
            "model_used": m.get("model_used"),
            "tokens_in": m.get("tokens_in"),
            "tokens_out": m.get("tokens_out"),
            "is_interrupted": m.get("is_interrupted", False),
            "created_at": dt.isoformat() if hasattr(dt, "isoformat") else str(dt)
        })

    return {
        "status": "success",
        "conversation": {
            "id": conv["id"],
            "title": conv.get("title", "Conversation"),
            "total_tokens_in": conv.get("total_tokens_in", 0),
            "total_tokens_out": conv.get("total_tokens_out", 0),
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
    Hardened for normalized error propagation, token accounting, cancellation safety,
    and zero automatic mock fallback.
    """
    user_id = str(current_user["_id"])
    user_name = current_user.get("full_name") or current_user.get("username", "User")

    # 1. Resolve provider and validate configuration upfront
    provider_id = req.provider or "gemini"
    try:
        provider = ai_engine_service.get_provider(provider_id)
    except AIProviderException as e:
        raise HTTPException(status_code=e.status_code or 400, detail=e.to_dict())

    model = req.model or (provider.get_supported_models()[0]["id"] if provider.get_supported_models() else "default")

    # 2. Load or create conversation thread
    first_title = req.prompt[:30].strip() + ("..." if len(req.prompt) > 30 else "")
    conv = await ai_engine_service.get_or_create_conversation(
        user_id=user_id,
        conversation_id=req.conversation_id,
        title=first_title
    )
    conv_id = conv["id"]

    # 3. Persist user prompt
    await ai_engine_service.append_message(
        user_id=user_id,
        conversation_id=conv_id,
        role="user",
        content=req.prompt
    )

    # 4. Assemble context window & system instructions
    history = conv.get("messages", []) + [{"role": "user", "content": req.prompt}]
    context = await ai_engine_service.prune_context_window(history, max_messages=10)
    system_instruction = ai_engine_service.build_system_instruction(
        user_locale=req.locale or "en",
        user_name=user_name
    )

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
        tokens_in = None
        tokens_out = None
        is_interrupted = False

        try:
            async for item in provider.stream_chat(
                messages=context,
                model=model,
                temperature=req.temperature or 0.7,
                system_instruction=system_instruction
            ):
                item_type = item.get("type", "chunk")
                if item_type == "chunk":
                    chunk_text = item.get("text", "")
                    full_response_acc.append(chunk_text)
                    yield f"data: {json.dumps({'type': 'chunk', 'text': chunk_text})}\n\n"
                elif item_type == "token_usage":
                    tokens_in = item.get("tokens_in")
                    tokens_out = item.get("tokens_out")
                    yield f"data: {json.dumps({'type': 'usage', 'tokens_in': tokens_in, 'tokens_out': tokens_out})}\n\n"

            full_text = "".join(full_response_acc)
            # Persist assistant completion to MongoDB
            await ai_engine_service.append_message(
                user_id=user_id,
                conversation_id=conv_id,
                role="assistant",
                content=full_text,
                model_used=model,
                tokens_in=tokens_in,
                tokens_out=tokens_out or len(full_text.split()),
                is_interrupted=False
            )
            yield f"data: {json.dumps({'type': 'done', 'full_length': len(full_text)})}\n\n"

        except AIProviderException as e:
            logger.warning(f"AI Provider error in stream: {e.code} - {e.message}")
            is_interrupted = True
            partial_text = "".join(full_response_acc)
            if partial_text:
                await ai_engine_service.append_message(
                    user_id=user_id,
                    conversation_id=conv_id,
                    role="assistant",
                    content=partial_text,
                    model_used=model,
                    is_interrupted=True
                )
            yield f"data: {json.dumps({'type': 'error', 'error_code': e.code.value, 'message': e.message, 'retryable': e.retryable})}\n\n"

        except Exception as e:
            logger.error(f"Unexpected error during AI streaming: {e}")
            is_interrupted = True
            yield f"data: {json.dumps({'type': 'error', 'error_code': AIErrorCode.UNKNOWN_PROVIDER_ERROR.value, 'message': 'An internal error occurred during inference.'})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
