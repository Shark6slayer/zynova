import logging
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
import uuid

from app.core.config import settings
from app.core.ai_errors import AIErrorCode, AIProviderException
from app.services.ai_providers import (
    BaseAIProvider,
    MockAIProvider,
    GeminiProvider,
    OpenAIProvider,
    AnthropicProvider,
)
from app.database.client import get_database

logger = logging.getLogger("zynova.ai_engine")

class AIEngineService:
    """
    Central orchestration service for Zynova AI Core Engine (Hardened).
    Enforces:
    - No automatic mock fallback in production: provider failures raise explicit normalized exceptions.
    - Token tracking and cost accounting in Mongo.
    - Owner-isolated conversation persistence.
    - Dynamic context window bounding.
    """

    def __init__(self):
        self.providers: Dict[str, BaseAIProvider] = {
            "mock": MockAIProvider(timeout_seconds=settings.AI_INFERENCE_TIMEOUT_SECONDS),
            "gemini": GeminiProvider(api_key=settings.GEMINI_API_KEY, timeout_seconds=settings.AI_INFERENCE_TIMEOUT_SECONDS),
            "openai": OpenAIProvider(api_key=settings.OPENAI_API_KEY, timeout_seconds=settings.AI_INFERENCE_TIMEOUT_SECONDS),
            "anthropic": AnthropicProvider(api_key=settings.ANTHROPIC_API_KEY, timeout_seconds=settings.AI_INFERENCE_TIMEOUT_SECONDS),
        }

    def get_provider(self, provider_id: str) -> BaseAIProvider:
        """
        Returns the requested provider.
        CRITICAL HARDENING: Never silently fallback to mock if a real provider is requested.
        """
        if provider_id not in self.providers:
            raise AIProviderException(
                code=AIErrorCode.INVALID_REQUEST,
                message=f"Provider '{provider_id}' is not supported.",
                provider_id=provider_id,
                status_code=400
            )

        provider = self.providers[provider_id]
        if not provider.is_configured():
            if provider_id == "mock":
                raise AIProviderException(
                    code=AIErrorCode.MOCK_DISABLED_IN_PROD,
                    message="Mock sandbox is disabled in production.",
                    provider_id="mock",
                    status_code=403
                )
            raise AIProviderException(
                code=AIErrorCode.AUTHENTICATION_ERROR,
                message=f"Provider '{provider_id}' is not configured on this server.",
                provider_id=provider_id,
                status_code=401
            )

        return provider

    def list_available_models(self) -> List[Dict[str, Any]]:
        """Returns consolidated models with configuration and sandbox status."""
        available = []
        for pid, provider in self.providers.items():
            is_conf = provider.is_configured()
            for m in provider.get_supported_models():
                available.append({
                    **m,
                    "provider": pid,
                    "provider_name": provider.display_name,
                    "is_configured": is_conf,
                    "is_active_default": (pid == settings.AI_DEFAULT_PROVIDER and m["id"] == settings.AI_DEFAULT_MODEL)
                })
        return available

    def build_system_instruction(self, user_locale: str = "en", user_name: Optional[str] = None) -> str:
        """Constructs sovereign Indic system instruction enforcing respect and language fidelity."""
        name_str = f" Addressing user as: {user_name}." if user_name else ""
        return (
            "You are Zynova AI, a sovereign multilingual assistant built for India. "
            f"User preferred language/locale is '{user_locale}'.{name_str} "
            "Respond naturally in the language or dialect used by the user (including Tamil, Tanglish, Hindi, Telugu, Kannada, Malayalam, etc.). "
            "Be concise, helpful, mathematically rigorous, and adhere strictly to factual correctness. "
            "Never fabricate financial transactions, health advice, or legal counsel. Format code in clean Markdown blocks."
        )

    async def get_conversation_by_id(self, user_id: str, conversation_id: str) -> Optional[Dict[str, Any]]:
        """Loads an existing conversation strictly verifying user ownership."""
        db = get_database()
        return await db.ai_conversations.find_one({"id": conversation_id, "user_id": user_id})

    async def get_or_create_conversation(self, user_id: str, conversation_id: Optional[str] = None, title: Optional[str] = None) -> Dict[str, Any]:
        """Loads an existing conversation or initializes a new one in MongoDB."""
        db = get_database()
        if conversation_id:
            conv = await db.ai_conversations.find_one({"id": conversation_id, "user_id": user_id})
            if conv:
                return conv

        new_id = conversation_id or f"ai_conv_{uuid.uuid4().hex[:12]}"
        conv_doc = {
            "id": new_id,
            "user_id": user_id,
            "title": title or "New Conversation",
            "created_at": datetime.now(timezone.utc),
            "updated_at": datetime.now(timezone.utc),
            "messages": [],
            "message_count": 0,
            "total_tokens_in": 0,
            "total_tokens_out": 0,
            "is_archived": False
        }
        await db.ai_conversations.insert_one(conv_doc)
        return conv_doc

    async def append_message(
        self,
        user_id: str,
        conversation_id: str,
        role: str,
        content: str,
        model_used: Optional[str] = None,
        tokens_in: Optional[int] = None,
        tokens_out: Optional[int] = None,
        is_interrupted: bool = False
    ) -> None:
        """Appends a message to the conversation and updates token accounting."""
        db = get_database()
        msg_obj = {
            "id": f"msg_{uuid.uuid4().hex[:10]}",
            "role": role,
            "content": content,
            "model_used": model_used,
            "tokens_in": tokens_in,
            "tokens_out": tokens_out,
            "is_interrupted": is_interrupted,
            "created_at": datetime.now(timezone.utc)
        }
        update_fields: Dict[str, Any] = {
            "$push": {"messages": msg_obj},
            "$inc": {
                "message_count": 1,
                "total_tokens_in": tokens_in or 0,
                "total_tokens_out": tokens_out or 0
            },
            "$set": {"updated_at": datetime.now(timezone.utc)}
        }
        await db.ai_conversations.update_one(
            {"id": conversation_id, "user_id": user_id},
            update_fields
        )

    async def prune_context_window(self, messages: List[Dict[str, Any]], max_messages: int = 10) -> List[Dict[str, str]]:
        """Ensures the context window stays within token boundaries by keeping recent turns."""
        recent = messages[-max_messages:] if len(messages) > max_messages else messages
        formatted = []
        for m in recent:
            formatted.append({
                "role": m.get("role", "user"),
                "content": m.get("content", "")
            })
        return formatted

    async def list_user_conversations(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Lists active conversations for the user sorted by latest activity."""
        db = get_database()
        cursor = db.ai_conversations.find(
            {"user_id": user_id, "is_archived": {"$ne": True}},
            {"_id": 0, "messages": {"$slice": -1}}  # Only return the last message for preview
        ).sort("updated_at", -1).limit(limit)
        return await cursor.to_list(length=limit)

    async def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        """Deletes a user-owned conversation."""
        db = get_database()
        res = await db.ai_conversations.delete_one({"id": conversation_id, "user_id": user_id})
        return res.deleted_count > 0

ai_engine_service = AIEngineService()
