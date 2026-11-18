"""
C:/super_ai/backend/tests/test_zenolm_sovereign_provider.py - Phase 8.2 Sovereign ZenoLM Provider Test Suite

Remediates FIND-04:
- Verifies native ZenoLMProvider in app/services/ai_providers.py.
- Validates local PyTorch inference without commercial 3rd-party API dependencies.
- Confirms registration in AIEngineService and sovereign default in /api/v1/ai/chat/stream.
"""

import os
import sys
import pytest
import asyncio

from app.core.config import settings
from app.services.ai_providers import ZenoLMProvider
from app.services.ai_engine_service import AIEngineService


@pytest.fixture
def zenolm_provider():
    return ZenoLMProvider()


@pytest.fixture
def ai_engine():
    return AIEngineService()


def test_zenolm_provider_configuration(zenolm_provider):
    """Verifies that ZenoLMProvider detects local weights and vocab."""
    assert zenolm_provider.provider_id == "zenolm"
    assert zenolm_provider.is_configured() is True

    models = zenolm_provider.get_supported_models()
    assert len(models) >= 1
    assert models[0]["id"] == "zenolm-micro-2m"
    assert models[0]["is_sovereign"] is True
    assert models[0]["cost_per_1k_input_paise"] == 0


def test_ai_engine_service_registration(ai_engine):
    """Verifies that AIEngineService contains 'zenolm' as a supported provider."""
    assert "zenolm" in ai_engine.providers
    provider = ai_engine.get_provider("zenolm")
    assert isinstance(provider, ZenoLMProvider)

    models = ai_engine.list_available_models()
    zeno_models = [m for m in models if m["provider"] == "zenolm"]
    assert len(zeno_models) >= 1
    assert zeno_models[0]["is_configured"] is True
    assert zeno_models[0]["is_active_default"] is True


@pytest.mark.asyncio
async def test_zenolm_stream_chat_local_inference(zenolm_provider):
    """Verifies local streaming inference from ZenoLM without any network calls."""
    messages = [
        {"role": "user", "content": "Wake me up at 6:30 AM"}
    ]
    chunks = []
    usages = []

    async for item in zenolm_provider.stream_chat(
        messages=messages,
        model="zenolm-micro-2m",
        temperature=0.0,
        max_tokens=32
    ):
        if item.get("type") == "chunk":
            chunks.append(item.get("text", ""))
        elif item.get("type") == "token_usage":
            usages.append(item)

    full_output = "".join(chunks)
    assert len(chunks) > 0
    assert len(usages) >= 2
    assert usages[0]["tokens_in"] > 0
    assert usages[-1]["tokens_out"] > 0
    print(f"\n[ZenoLM Streaming Output]: {full_output}")


def test_zenolm_provider_gpu_placement(zenolm_provider):
    """Verifies that ZenoLMProvider places model strictly on CUDA under GPU-first policy."""
    import torch
    if torch.cuda.is_available():
        assert zenolm_provider.device.type == "cuda"
        zenolm_provider._ensure_loaded()
        assert zenolm_provider._device.type == "cuda"
        for p in zenolm_provider._model.parameters():
            assert p.is_cuda is True


@pytest.mark.asyncio
async def test_zenolm_provider_rejects_cpu_fallback_by_default(monkeypatch):
    """Verifies that ZenoLMProvider refuses silent CPU fallback when GPU is disabled."""
    import torch
    from app.core.ai_errors import AIProviderException, AIErrorCode
    from zeno_lm.device_manager import DeviceManager, GPUUnavailableError

    # Force CUDA unavailable
    monkeypatch.setattr(torch.cuda, "is_available", lambda: False)
    DeviceManager.reset_instance()

    provider = ZenoLMProvider()
    with pytest.raises((AIProviderException, GPUUnavailableError)) as exc_info:
        provider._ensure_loaded()

    # Must raise AIProviderException with GPU_UNAVAILABLE or GPUUnavailableError
    err_str = str(exc_info.value)
    assert "GPU" in err_str or "CUDA" in err_str or "GPU_UNAVAILABLE" in err_str

    # Reset DeviceManager
    DeviceManager.reset_instance()


@pytest.mark.asyncio
async def test_zenolm_100m_sovereign_inference(zenolm_provider):
    """Verifies sovereign local streaming inference using the 100M foundation model on GPU."""
    if not os.path.exists("C:/zenoai/checkpoints/zeno_lm_100m.pt"):
        pytest.skip("100M checkpoint not present")

    messages = [
        {"role": "user", "content": "Hello ZenoLM 100M"}
    ]
    chunks = []
    usages = []

    async for item in zenolm_provider.stream_chat(
        messages=messages,
        model="zenolm-100m",
        temperature=0.0,
        max_tokens=16
    ):
        if item.get("type") == "chunk":
            chunks.append(item.get("text", ""))
        elif item.get("type") == "token_usage":
            usages.append(item)

    assert len(chunks) > 0
    assert len(usages) >= 2
    assert usages[0]["tokens_in"] > 0
    assert usages[-1]["tokens_out"] > 0
    assert zenolm_provider._active_model_id == "zenolm-100m"
    assert zenolm_provider._device.type == "cuda"
    assert next(zenolm_provider._model.parameters()).is_cuda is True


@pytest.mark.asyncio
async def test_zenolm_100m_p85_enhanced_inference(zenolm_provider):
    """Verifies sovereign local streaming inference using the Phase 8.5 enhanced model on CUDA."""
    if not os.path.exists("C:/zenoai/checkpoints/phase_8_5/zeno_lm_100m_p85_final.pt"):
        pytest.skip("Phase 8.5 checkpoint not present")

    messages = [
        {"role": "user", "content": "Explain machine learning in one sentence."}
    ]
    chunks = []
    usages = []

    async for item in zenolm_provider.stream_chat(
        messages=messages,
        model="zenolm-100m-p85",
        temperature=0.0,
        max_tokens=16
    ):
        if item.get("type") == "chunk":
            chunks.append(item.get("text", ""))
        elif item.get("type") == "token_usage":
            usages.append(item)

    assert len(chunks) > 0
    assert len(usages) >= 2
    assert usages[0]["tokens_in"] > 0
    assert usages[-1]["tokens_out"] > 0
    assert zenolm_provider._active_model_id == "zenolm-100m-p85"
    assert zenolm_provider._device.type == "cuda"
    assert next(zenolm_provider._model.parameters()).is_cuda is True


@pytest.mark.asyncio
async def test_zenolm_100m_p86_multilingual_inference(zenolm_provider):
    """Verifies sovereign local streaming inference using the Phase 8.6 multilingual model on CUDA."""
    if not os.path.exists("C:/zenoai/checkpoints/phase_8_6/zeno_lm_100m_p86_final.pt"):
        pytest.skip("Phase 8.6 checkpoint not present")

    messages = [
        {"role": "user", "content": "வணக்கம் ZenoAI! Explain photosynthesis."}
    ]
    chunks = []
    usages = []

    async for item in zenolm_provider.stream_chat(
        messages=messages,
        model="zenolm-100m-p86",
        temperature=0.0,
        max_tokens=16
    ):
        if item.get("type") == "chunk":
            chunks.append(item.get("text", ""))
        elif item.get("type") == "token_usage":
            usages.append(item)

    assert len(chunks) > 0
    assert len(usages) >= 2
    assert usages[0]["tokens_in"] > 0
    assert usages[-1]["tokens_out"] > 0
    assert zenolm_provider._active_model_id == "zenolm-100m-p86"
    assert zenolm_provider._device.type == "cuda"
    assert next(zenolm_provider._model.parameters()).is_cuda is True
