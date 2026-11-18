import abc
import os
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


class ZenoLMProvider(BaseAIProvider):
    """
    Sovereign AI Provider executing ZenoLM foundation model locally via PyTorch CUDA.
    Remediates FIND-04: Full independence from commercial 3rd-party inference APIs (Gemini, OpenAI, Anthropic).
    """
    provider_id = "zenolm"
    display_name = "ZenoLM Sovereign Neural Engine (PyTorch Local)"

    def __init__(
        self,
        checkpoint_path: Optional[str] = None,
        vocab_path: Optional[str] = None,
        timeout_seconds: float = 45.0,
        device: Optional[str] = None
    ):
        super().__init__(api_key=None, timeout_seconds=timeout_seconds)
        self.checkpoint_path = checkpoint_path or getattr(settings, "ZENOLM_CHECKPOINT_PATH", "C:/zenoai/checkpoints/zeno_lm_p8_2_torch_best.pt")
        self.vocab_path = vocab_path or getattr(settings, "ZENOLM_VOCAB_PATH", "C:/zenoai/checkpoints/zeno_tokenizer_vocab.json")
        self._model = None
        self._tokenizer = None
        self._device = device
        self._initialized = False
        self._init_error = None

    @property
    def device(self):
        if self._device is not None:
            return self._device
        import torch
        if torch.cuda.is_available():
            return torch.device("cuda:0")
        return torch.device("cpu")

    def _ensure_loaded(self, model_id: Optional[str] = None):
        target_ckpt = self.checkpoint_path
        target_vocab = self.vocab_path
        if model_id in ["zenolm-100m", "zenolm-100m-p85", "zenolm-100m-p86"]:
            if model_id == "zenolm-100m-p86" and os.path.exists("C:/zenoai/checkpoints/phase_8_6/zeno_lm_100m_p86_final.pt"):
                target_ckpt = "C:/zenoai/checkpoints/phase_8_6/zeno_lm_100m_p86_final.pt"
            elif model_id == "zenolm-100m-p85" and os.path.exists("C:/zenoai/checkpoints/phase_8_5/zeno_lm_100m_p85_final.pt"):
                target_ckpt = "C:/zenoai/checkpoints/phase_8_5/zeno_lm_100m_p85_final.pt"
            elif os.path.exists("C:/zenoai/checkpoints/phase_8_6/zeno_lm_100m_p86_final.pt"):
                target_ckpt = "C:/zenoai/checkpoints/phase_8_6/zeno_lm_100m_p86_final.pt"
            elif os.path.exists("C:/zenoai/checkpoints/phase_8_5/zeno_lm_100m_p85_final.pt"):
                target_ckpt = "C:/zenoai/checkpoints/phase_8_5/zeno_lm_100m_p85_final.pt"
            elif os.path.exists("C:/zenoai/checkpoints/zeno_lm_100m.pt"):
                target_ckpt = "C:/zenoai/checkpoints/zeno_lm_100m.pt"
            target_vocab = "C:/zenoai/checkpoints/zeno_tokenizer_vocab_4k.json"

        req_model_id = model_id or "zenolm-micro-2m"
        if self._initialized and getattr(self, "_active_model_id", None) == req_model_id:
            return
        if not os.path.exists(target_ckpt) or not os.path.exists(target_vocab):
            self._init_error = f"Checkpoint ({target_ckpt}) or Vocab ({target_vocab}) missing"
            return
        try:
            import sys
            if "C:\\zenoai" not in sys.path:
                sys.path.insert(0, "C:\\zenoai")
            import torch
            from zeno_lm.config import ZenoLMConfig
            from zeno_lm.torch_model import ZenoLMModel
            from zeno_lm.tokenizer.bpe_tokenizer import ZenoTokenizer
            from zeno_lm.device_manager import DeviceManager, GPUUnavailableError

            allow_cpu = getattr(settings, "AI_ALLOW_CPU_FALLBACK", False)
            dm = DeviceManager.get_instance(allow_cpu_fallback=allow_cpu)
            dev = torch.device(self._device) if self._device else dm.get_device(0)

            ckpt = torch.load(target_ckpt, map_location=dev)
            cfg_dict = ckpt["config"]
            config = ZenoLMConfig(**cfg_dict)
            model = ZenoLMModel(config).to(dev)
            model.load_state_dict(ckpt["model_state_dict"])
            model.eval()

            # Verify parameter placement under GPU-first policy
            placement_audit = dm.verify_model_placement(model, expected_device_type=dev.type)
            if not placement_audit["is_verified"] and not allow_cpu:
                raise RuntimeError(f"GPU placement validation failed: {placement_audit['mismatched_tensors']}")

            tokenizer = ZenoTokenizer.load_vocabulary(target_vocab)
            self._model = model
            self._tokenizer = tokenizer
            self._device = dev
            self._active_model_id = req_model_id
            self._initialized = True
            logger.info(f"ZenoLMProvider loaded model {req_model_id} on {dev} from {target_ckpt}")
        except Exception as e:
            logger.error(f"Failed to load ZenoLM model: {e}")
            self._init_error = str(e)
            from zeno_lm.device_manager import GPUUnavailableError
            if isinstance(e, GPUUnavailableError):
                raise AIProviderException(
                    code=AIErrorCode.GPU_UNAVAILABLE,
                    message=str(e),
                    provider_id=self.provider_id,
                    status_code=503
                )

    def is_configured(self) -> bool:
        return os.path.exists(self.checkpoint_path) and os.path.exists(self.vocab_path)

    def get_supported_models(self) -> List[Dict[str, Any]]:
        models = [
            {
                "id": "zenolm-micro-2m",
                "name": "ZenoLM Micro 2M (Sovereign Local)",
                "context_window": 256,
                "cost_per_1k_input_paise": 0,
                "cost_per_1k_output_paise": 0,
                "indic_support": True,
                "is_sovereign": True
            }
        ]
        if os.path.exists("C:/zenoai/checkpoints/zeno_lm_100m.pt") or os.path.exists("C:/zenoai/checkpoints/phase_8_5/zeno_lm_100m_p85_final.pt"):
            models.append({
                "id": "zenolm-100m",
                "name": "ZenoLM 100M Foundation (Sovereign Local)",
                "context_window": 1024,
                "cost_per_1k_input_paise": 0,
                "cost_per_1k_output_paise": 0,
                "indic_support": True,
                "is_sovereign": True
            })
        if os.path.exists("C:/zenoai/checkpoints/phase_8_5/zeno_lm_100m_p85_final.pt"):
            models.append({
                "id": "zenolm-100m-p85",
                "name": "ZenoLM 100M Phase 8.5 Enhanced (Sovereign Local)",
                "context_window": 2048,
                "cost_per_1k_input_paise": 0,
                "cost_per_1k_output_paise": 0,
                "indic_support": True,
                "is_sovereign": True
            })
        if os.path.exists("C:/zenoai/checkpoints/phase_8_6/zeno_lm_100m_p86_final.pt"):
            models.append({
                "id": "zenolm-100m-p86",
                "name": "ZenoLM 100M Phase 8.6 Intelligence & Multilingual (Sovereign Local)",
                "context_window": 4096,
                "cost_per_1k_input_paise": 0,
                "cost_per_1k_output_paise": 0,
                "indic_support": True,
                "is_sovereign": True
            })
        return models

    async def stream_chat(
        self,
        messages: List[Dict[str, str]],
        model: str,
        temperature: float = 0.7,
        max_tokens: int = 256,
        system_instruction: Optional[str] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        self._ensure_loaded(model_id=model)
        if not self._initialized or self._model is None:
            err_msg = str(self._init_error)
            code = AIErrorCode.GPU_UNAVAILABLE if ("GPU" in err_msg or "CUDA" in err_msg) else AIErrorCode.MODEL_UNAVAILABLE
            raise AIProviderException(
                code=code,
                message=f"ZenoLM sovereign model unavailable: {err_msg}",
                provider_id=self.provider_id,
                model=model,
                status_code=503
            )

        # Assemble prompt with canonical special tokens
        prompt_parts = []
        if system_instruction:
            prompt_parts.append(f"<|start_system|> {system_instruction} <|end_system|>")
        for m in messages:
            role = m.get("role", "user")
            content = m.get("content", "")
            if role == "user":
                prompt_parts.append(f"<|start_user|> {content} <|end_user|>")
            elif role == "assistant":
                prompt_parts.append(f"<|start_assistant|> {content} <|end_assistant|>")
        prompt_parts.append("<|start_assistant|>")
        prompt_text = " ".join(prompt_parts)

        tokens = self._tokenizer.encode(prompt_text, add_special_tokens=True)
        tokens_in = len(tokens)

        yield {
            "type": "token_usage",
            "tokens_in": tokens_in,
            "tokens_out": 0,
            "is_estimated": False
        }

        # Autoregressive generation
        import torch
        import codecs
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        eos_id = self._tokenizer.special_token_to_id.get("<|end_of_text|>", 2)
        assistant_end_id = self._tokenizer.special_token_to_id.get("<|end_assistant|>")

        generated = list(tokens)
        new_token_count = 0

        with torch.no_grad():
            for _ in range(max_tokens):
                curr_input = torch.tensor([generated[-self._model.config.max_position_embeddings:]], dtype=torch.long, device=self._device)
                logits = self._model(curr_input)
                next_token_logits = logits[0, -1, :].clone()

                # Repetition penalty
                for prev_token in set(generated):
                    if next_token_logits[prev_token] < 0:
                        next_token_logits[prev_token] *= 1.15
                    else:
                        next_token_logits[prev_token] /= 1.15

                if temperature <= 0.01:
                    next_tok = torch.argmax(next_token_logits).item()
                else:
                    next_token_logits = next_token_logits / temperature
                    probs = torch.softmax(next_token_logits, dim=-1)
                    next_tok = torch.multinomial(probs, num_samples=1).item()

                generated.append(next_tok)
                new_token_count += 1

                # Incremental UTF-8 decoding to prevent broken multi-byte characters
                if next_tok in self._tokenizer.id_to_special_token:
                    tok_text = self._tokenizer.id_to_special_token[next_tok]
                    if tok_text not in ["<|end_of_text|>", "<|end_assistant|>", "<|pad|>"]:
                        yield {"type": "chunk", "text": tok_text}
                elif next_tok in self._tokenizer.id_to_vocab:
                    raw_b = self._tokenizer.id_to_vocab[next_tok]
                    tok_text = decoder.decode(raw_b, final=False)
                    if tok_text:
                        yield {"type": "chunk", "text": tok_text}

                if next_tok == eos_id or (assistant_end_id is not None and next_tok == assistant_end_id):
                    break

        tail = decoder.decode(b"", final=True)
        if tail:
            yield {"type": "chunk", "text": tail}

        yield {
            "type": "token_usage",
            "tokens_in": tokens_in,
            "tokens_out": new_token_count,
            "is_estimated": False
        }
