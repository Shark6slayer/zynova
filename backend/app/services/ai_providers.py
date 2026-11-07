import abc
import json
import logging
from typing import AsyncGenerator, Dict, Any, List, Optional
import httpx

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
    ) -> AsyncGenerator[str, None]:
        """Streams text chunks as they arrive from the inference provider."""
        pass


class MockAIProvider(BaseAIProvider):
    """
    Deterministic mock provider for CI testing and offline local sandbox environments.
    Guarantees reliable testing without incurring commercial API costs or network dependencies.
    """
    provider_id = "mock"
    display_name = "Zynova Mock Testing Provider"

    def is_configured(self) -> bool:
        return True

    def get_supported_models(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "mock-indic-v1",
                "name": "Zynova Mock Indic v1",
                "context_window": 4096,
                "cost_per_1k_input_paise": 0,
                "cost_per_1k_output_paise": 0,
                "indic_support": True,
            }
        ]

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        system_instruction: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        last_prompt = messages[-1]["content"] if messages else "Hello"
        mock_chunks = [
            f"[MockAI] Received prompt: '{last_prompt[:30]}...'. ",
            "Processing multilingual Indic context. ",
            "வணக்கம்! நான் Zynova AI. ",
            "Your sovereign request has been processed successfully."
        ]
        for chunk in mock_chunks:
            yield chunk


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
            },
            {
                "id": "gemini-2.5-pro",
                "name": "Gemini 2.5 Pro (Deep Reasoning)",
                "context_window": 2097152,
                "cost_per_1k_input_paise": 150,
                "cost_per_1k_output_paise": 600,
                "indic_support": True,
            }
        ]

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        system_instruction: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        if not self.is_configured():
            yield "Gemini API key is not configured on this server. Contact your administrator."
            return

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

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            async with client.stream("POST", url, json=payload) as response:
                if response.status_code != 200:
                    err_body = await response.aread()
                    logger.error(f"Gemini API error {response.status_code}: {err_body.decode(errors='ignore')}")
                    yield f"Error from Gemini API (HTTP {response.status_code}). Please verify your quota and API key."
                    return

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        parsed = json.loads(data_str)
                        candidates = parsed.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            for p in parts:
                                if "text" in p:
                                    yield p["text"]
                    except Exception as e:
                        logger.warning(f"Failed to parse Gemini SSE chunk: {e}")


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
            },
            {
                "id": "gpt-4o",
                "name": "GPT-4o Omnimodel",
                "context_window": 128000,
                "cost_per_1k_input_paise": 250,
                "cost_per_1k_output_paise": 1000,
                "indic_support": True,
            }
        ]

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        system_instruction: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        if not self.is_configured():
            yield "OpenAI API key is not configured on this server."
            return

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
            "stream": True
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            async with client.stream("POST", "https://api.openai.com/v1/chat/completions", json=payload, headers=headers) as response:
                if response.status_code != 200:
                    err_body = await response.aread()
                    logger.error(f"OpenAI API error {response.status_code}: {err_body.decode(errors='ignore')}")
                    yield f"Error from OpenAI API (HTTP {response.status_code})."
                    return

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    try:
                        parsed = json.loads(data_str)
                        delta = parsed.get("choices", [{}])[0].get("delta", {})
                        if "content" in delta:
                            yield delta["content"]
                    except Exception:
                        pass


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
            },
            {
                "id": "claude-3-5-sonnet-latest",
                "name": "Claude 3.5 Sonnet",
                "context_window": 200000,
                "cost_per_1k_input_paise": 300,
                "cost_per_1k_output_paise": 1500,
                "indic_support": True,
            }
        ]

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 2048,
        system_instruction: Optional[str] = None
    ) -> AsyncGenerator[str, None]:
        if not self.is_configured():
            yield "Anthropic API key is not configured on this server."
            return

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

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            async with client.stream("POST", "https://api.anthropic.com/v1/messages", json=payload, headers=headers) as response:
                if response.status_code != 200:
                    err_body = await response.aread()
                    logger.error(f"Anthropic API error {response.status_code}: {err_body.decode(errors='ignore')}")
                    yield f"Error from Anthropic API (HTTP {response.status_code})."
                    return

                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    data_str = line[6:].strip()
                    try:
                        parsed = json.loads(data_str)
                        if parsed.get("type") == "content_block_delta":
                            delta = parsed.get("delta", {})
                            if delta.get("type") == "text_delta":
                                yield delta.get("text", "")
                    except Exception:
                        pass
