import abc
import json
import logging
from typing import AsyncGenerator, Dict, Any, List, Optional
import httpx

from app.core.config import settings
from app.core.ai_errors import AIErrorCode, AIProviderException

logger = logging.getLogger("zynova.ai_engine")

class BaseAIProvider(abc.ABC):
    """
    Abstract interface for AI model providers.
    Supports asynchronous token streaming, standard completions, and health/readiness checks.
    """
    provider_id: str
    display_name: str

    def __init__(self, api_key: Optional[str] = None, timeout_seconds: float = 45.0):
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    @abc.abstractmethod
    def is_configured(self) -> bool:
        """Returns True if the provider has credentials or local engine configured."""
        pass

    @abc.abstractmethod
    def get_supported_models(self) -> List[Dict[str, Any]]:
        """Returns catalogue of supported models with cost and context limit metadata."""
        pass

    @abc.abstractmethod
    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        system_instruction: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """
        Streams structured token chunks as they arrive from the inference provider.
        Yields dicts with:
        - type: 'chunk', 'token_usage', or 'interrupted'
        - text: string piece
        - tokens_in / tokens_out: int count if known
        """
        pass


class MockAIProvider(BaseAIProvider):
    """
    Deterministic mock provider for CI testing and offline local sandbox environments.
    Strictly gated by `settings.AI_MOCK_MODE`. In production, attempting to invoke
    this provider raises `MOCK_DISABLED_IN_PROD` unless explicitly permitted.
    """
    provider_id = "mock"
    display_name = "Zynova Mock Testing Sandbox"

    def is_configured(self) -> bool:
        # Mock provider is only available if explicitly enabled via AI_MOCK_MODE
        return bool(settings.AI_MOCK_MODE)

    def get_supported_models(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "mock-indic-v1",
                "name": "Zynova Mock Sandbox v1",
                "context_window": 4096,
                "cost_per_1k_input_paise": 0,
                "cost_per_1k_output_paise": 0,
                "indic_support": True,
                "is_sandbox": True
            }
        ]

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        system_instruction: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if not self.is_configured():
            raise AIProviderException(
                code=AIErrorCode.MOCK_DISABLED_IN_PROD,
                message="Mock AI provider is disabled in production. Configure a real provider or set AI_MOCK_MODE=true for testing.",
                provider_id=self.provider_id,
                model=model,
                status_code=403,
                retryable=False
            )

        last_prompt = messages[-1]["content"] if messages else "Hello"
        mock_chunks = [
            f"[Zynova Mock Sandbox] Received: '{last_prompt[:30]}...'. ",
            "Context validated. ",
            "வணக்கம்! நான் Zynova AI (Sandbox Mode). ",
            "Inference completed cleanly."
        ]
        total_out = sum(len(c.split()) for c in mock_chunks)
        total_in = sum(len(m.get("content", "").split()) for m in messages)

        for chunk in mock_chunks:
            yield {"type": "chunk", "text": chunk}

        yield {
            "type": "token_usage",
            "tokens_in": total_in,
            "tokens_out": total_out,
            "is_estimated": True
        }


class GeminiProvider(BaseAIProvider):
    """
    Official Google Gemini API provider using direct HTTP streaming endpoints.
    Provides fast token streaming across all Indic languages (Tamil, Hindi, Telugu, etc.).
    """
    provider_id = "gemini"
    display_name = "Google Gemini"

    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def get_supported_models(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "gemini-2.5-flash",
                "name": "Gemini 2.5 Flash (Fast Multilingual)",
                "context_window": 1048576,
                "cost_per_1k_input_paise": 10,
                "cost_per_1k_output_paise": 40,
                "indic_support": True,
                "is_sandbox": False
            },
            {
                "id": "gemini-2.5-pro",
                "name": "Gemini 2.5 Pro (Deep Reasoning)",
                "context_window": 2097152,
                "cost_per_1k_input_paise": 150,
                "cost_per_1k_output_paise": 600,
                "indic_support": True,
                "is_sandbox": False
            }
        ]

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        system_instruction: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if not self.is_configured():
            raise AIProviderException(
                code=AIErrorCode.AUTHENTICATION_ERROR,
                message="Google Gemini API key is not configured on this server.",
                provider_id=self.provider_id,
                model=model,
                status_code=401,
                retryable=False
            )

        # Format messages for Gemini API
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({
                "role": role,
                "parts": [{"text": msg["content"]}]
            })

        payload: Dict[str, Any] = {
            "contents": contents,
            "generationConfig": {
                "temperature": temperature,
                "maxOutputTokens": max_tokens,
            }
        }
        if system_instruction:
            payload["systemInstruction"] = {
                "parts": [{"text": system_instruction}]
            }

        url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent?key={self.api_key}&alt=sse"

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                async with client.stream("POST", url, json=payload) as response:
                    if response.status_code == 400:
                        raise AIProviderException(
                            code=AIErrorCode.INVALID_REQUEST,
                            message="Invalid request payload or model configuration.",
                            provider_id=self.provider_id,
                            model=model,
                            status_code=400
                        )
                    elif response.status_code in (401, 403):
                        raise AIProviderException(
                            code=AIErrorCode.AUTHENTICATION_ERROR,
                            message="Authentication failed with Google Gemini API.",
                            provider_id=self.provider_id,
                            model=model,
                            status_code=response.status_code
                        )
                    elif response.status_code == 404:
                        raise AIProviderException(
                            code=AIErrorCode.MODEL_UNAVAILABLE,
                            message=f"Model '{model}' is not available on Gemini API.",
                            provider_id=self.provider_id,
                            model=model,
                            status_code=404
                        )
                    elif response.status_code == 429:
                        raise AIProviderException(
                            code=AIErrorCode.RATE_LIMIT_ERROR,
                            message="Google Gemini API rate limit or quota exceeded.",
                            provider_id=self.provider_id,
                            model=model,
                            status_code=429,
                            retryable=True
                        )
                    elif response.status_code != 200:
                        raise AIProviderException(
                            code=AIErrorCode.PROVIDER_UNAVAILABLE,
                            message=f"Google Gemini upstream returned HTTP {response.status_code}.",
                            provider_id=self.provider_id,
                            model=model,
                            status_code=response.status_code,
                            retryable=True
                        )

                    usage_reported = False
                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            parsed = json.loads(data_str)
                            # Extract usage metadata if present in stream
                            usage_meta = parsed.get("usageMetadata")
                            if usage_meta and not usage_reported:
                                yield {
                                    "type": "token_usage",
                                    "tokens_in": usage_meta.get("promptTokenCount", 0),
                                    "tokens_out": usage_meta.get("candidatesTokenCount", 0),
                                    "is_estimated": False
                                }
                                usage_reported = True

                            candidates = parsed.get("candidates", [])
                            if candidates:
                                parts = candidates[0].get("content", {}).get("parts", [])
                                for p in parts:
                                    if "text" in p:
                                        yield {"type": "chunk", "text": p["text"]}
                        except Exception as e:
                            logger.warning(f"Failed to parse Gemini SSE chunk: {e}")

        except httpx.TimeoutException:
            raise AIProviderException(
                code=AIErrorCode.PROVIDER_TIMEOUT,
                message=f"Gemini API timed out after {self.timeout_seconds}s.",
                provider_id=self.provider_id,
                model=model,
                status_code=504,
                retryable=True
            )
        except httpx.RequestError as e:
            raise AIProviderException(
                code=AIErrorCode.PROVIDER_UNAVAILABLE,
                message="Network error connecting to Gemini upstream service.",
                provider_id=self.provider_id,
                model=model,
                status_code=503,
                retryable=True
            )


class OpenAIProvider(BaseAIProvider):
    """
    OpenAI API provider for GPT-4o / GPT-4o-mini models.
    """
    provider_id = "openai"
    display_name = "OpenAI"

    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def get_supported_models(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "gpt-4o-mini",
                "name": "GPT-4o Mini",
                "context_window": 128000,
                "cost_per_1k_input_paise": 15,
                "cost_per_1k_output_paise": 60,
                "indic_support": True,
                "is_sandbox": False
            },
            {
                "id": "gpt-4o",
                "name": "GPT-4o Omnimodel",
                "context_window": 128000,
                "cost_per_1k_input_paise": 250,
                "cost_per_1k_output_paise": 1000,
                "indic_support": True,
                "is_sandbox": False
            }
        ]

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        system_instruction: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if not self.is_configured():
            raise AIProviderException(
                code=AIErrorCode.AUTHENTICATION_ERROR,
                message="OpenAI API key is not configured on this server.",
                provider_id=self.provider_id,
                model=model,
                status_code=401,
                retryable=False
            )

        chat_messages = []
        if system_instruction:
            chat_messages.append({"role": "system", "content": system_instruction})
        for msg in messages:
            chat_messages.append({"role": msg["role"], "content": msg["content"]})

        payload = {
            "model": model,
            "messages": chat_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": True,
            "stream_options": {"include_usage": True}
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                async with client.stream("POST", "https://api.openai.com/v1/chat/completions", json=payload, headers=headers) as response:
                    if response.status_code in (401, 403):
                        raise AIProviderException(
                            code=AIErrorCode.AUTHENTICATION_ERROR,
                            message="Invalid OpenAI API key or unauthorized organization.",
                            provider_id=self.provider_id,
                            model=model,
                            status_code=response.status_code
                        )
                    elif response.status_code == 404:
                        raise AIProviderException(
                            code=AIErrorCode.MODEL_UNAVAILABLE,
                            message=f"Model '{model}' is not available on OpenAI API.",
                            provider_id=self.provider_id,
                            model=model,
                            status_code=404
                        )
                    elif response.status_code == 429:
                        raise AIProviderException(
                            code=AIErrorCode.RATE_LIMIT_ERROR,
                            message="OpenAI rate limit or usage quota exceeded.",
                            provider_id=self.provider_id,
                            model=model,
                            status_code=429,
                            retryable=True
                        )
                    elif response.status_code != 200:
                        raise AIProviderException(
                            code=AIErrorCode.PROVIDER_UNAVAILABLE,
                            message=f"OpenAI service returned HTTP {response.status_code}.",
                            provider_id=self.provider_id,
                            model=model,
                            status_code=response.status_code,
                            retryable=True
                        )

                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        if data_str == "[DONE]":
                            break
                        try:
                            parsed = json.loads(data_str)
                            # Extract usage if returned in stream
                            usage = parsed.get("usage")
                            if usage:
                                yield {
                                    "type": "token_usage",
                                    "tokens_in": usage.get("prompt_tokens", 0),
                                    "tokens_out": usage.get("completion_tokens", 0),
                                    "is_estimated": False
                                }
                            delta = parsed.get("choices", [{}])[0].get("delta", {})
                            if "content" in delta and delta["content"]:
                                yield {"type": "chunk", "text": delta["content"]}
                        except Exception:
                            pass

        except httpx.TimeoutException:
            raise AIProviderException(
                code=AIErrorCode.PROVIDER_TIMEOUT,
                message=f"OpenAI API timed out after {self.timeout_seconds}s.",
                provider_id=self.provider_id,
                model=model,
                status_code=504,
                retryable=True
            )
        except httpx.RequestError:
            raise AIProviderException(
                code=AIErrorCode.PROVIDER_UNAVAILABLE,
                message="Network error connecting to OpenAI upstream service.",
                provider_id=self.provider_id,
                model=model,
                status_code=503,
                retryable=True
            )


class AnthropicProvider(BaseAIProvider):
    """
    Anthropic API provider for Claude 3.5 Sonnet / Haiku.
    """
    provider_id = "anthropic"
    display_name = "Anthropic Claude"

    def is_configured(self) -> bool:
        return bool(self.api_key and len(self.api_key.strip()) > 5)

    def get_supported_models(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "claude-3-5-haiku-latest",
                "name": "Claude 3.5 Haiku",
                "context_window": 200000,
                "cost_per_1k_input_paise": 80,
                "cost_per_1k_output_paise": 400,
                "indic_support": True,
                "is_sandbox": False
            },
            {
                "id": "claude-3-5-sonnet-latest",
                "name": "Claude 3.5 Sonnet",
                "context_window": 200000,
                "cost_per_1k_input_paise": 300,
                "cost_per_1k_output_paise": 1500,
                "indic_support": True,
                "is_sandbox": False
            }
        ]

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        system_instruction: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        if not self.is_configured():
            raise AIProviderException(
                code=AIErrorCode.AUTHENTICATION_ERROR,
                message="Anthropic API key is not configured on this server.",
                provider_id=self.provider_id,
                model=model,
                status_code=401,
                retryable=False
            )

        chat_messages = []
        for msg in messages:
            if msg["role"] in ["user", "assistant"]:
                chat_messages.append({"role": msg["role"], "content": msg["content"]})

        payload = {
            "model": model,
            "messages": chat_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True
        }
        if system_instruction:
            payload["system"] = system_instruction

        headers = {
            "x-api-key": self.api_key or "",
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                async with client.stream("POST", "https://api.anthropic.com/v1/messages", json=payload, headers=headers) as response:
                    if response.status_code in (401, 403):
                        raise AIProviderException(
                            code=AIErrorCode.AUTHENTICATION_ERROR,
                            message="Invalid Anthropic API key or unauthorized request.",
                            provider_id=self.provider_id,
                            model=model,
                            status_code=response.status_code
                        )
                    elif response.status_code == 404:
                        raise AIProviderException(
                            code=AIErrorCode.MODEL_UNAVAILABLE,
                            message=f"Model '{model}' is not available on Anthropic API.",
                            provider_id=self.provider_id,
                            model=model,
                            status_code=404
                        )
                    elif response.status_code == 429:
                        raise AIProviderException(
                            code=AIErrorCode.RATE_LIMIT_ERROR,
                            message="Anthropic rate limit or credit balance exhausted.",
                            provider_id=self.provider_id,
                            model=model,
                            status_code=429,
                            retryable=True
                        )
                    elif response.status_code != 200:
                        raise AIProviderException(
                            code=AIErrorCode.PROVIDER_UNAVAILABLE,
                            message=f"Anthropic service returned HTTP {response.status_code}.",
                            provider_id=self.provider_id,
                            model=model,
                            status_code=response.status_code,
                            retryable=True
                        )

                    async for line in response.aiter_lines():
                        if not line or not line.startswith("data: "):
                            continue
                        data_str = line[6:].strip()
                        try:
                            parsed = json.loads(data_str)
                            # Handle message_start usage
                            if parsed.get("type") == "message_start":
                                usage = parsed.get("message", {}).get("usage", {})
                                if usage:
                                    yield {
                                        "type": "token_usage",
                                        "tokens_in": usage.get("input_tokens", 0),
                                        "tokens_out": usage.get("output_tokens", 0),
                                        "is_estimated": False
                                    }
                            elif parsed.get("type") == "content_block_delta":
                                delta = parsed.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    yield {"type": "chunk", "text": delta.get("text", "")}
                        except Exception:
                            pass

        except httpx.TimeoutException:
            raise AIProviderException(
                code=AIErrorCode.PROVIDER_TIMEOUT,
                message=f"Anthropic API timed out after {self.timeout_seconds}s.",
                provider_id=self.provider_id,
                model=model,
                status_code=504,
                retryable=True
            )
        except httpx.RequestError:
            raise AIProviderException(
                code=AIErrorCode.PROVIDER_UNAVAILABLE,
                message="Network error connecting to Anthropic upstream service.",
                provider_id=self.provider_id,
                model=model,
                status_code=503,
                retryable=True
            )
