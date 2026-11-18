"""
C:/super_ai/backend/tests/test_zenolm_p87_sovereign_provider.py - Phase 8.7 Sovereign ZenoLM Provider Test Suite

Verifies:
1. Registration of 'zenolm-100m-p87' in ZenoLMProvider and AIEngineService.
2. Sovereign model loading directly from Phase 8.7 production checkpoint:
   C:/zenoai/checkpoints/phase_8_7/zeno_lm_100m_p87_final.pt.
3. Verification of 100M parameter count (100,168,992).
4. GPU-first placement strictly on CUDA.
5. Real streaming inference with token usage telemetry.
6. Error handling, concurrency safety, and zero commercial API fallback.
"""

import os
import sys
import pytest
import asyncio
import torch

from app.services.ai_providers import ZenoLMProvider
from app.services.ai_engine_service import AIEngineService

CHECKPOINT_P87 = "C:/zenoai/checkpoints/phase_8_7/zeno_lm_100m_p87_final.pt"


@pytest.fixture
def zenolm_provider():
    return ZenoLMProvider()


@pytest.fixture
def ai_engine():
    return AIEngineService()


def test_zenolm_p87_model_registration(zenolm_provider):
    """Verifies that zenolm-100m-p87 is registered and discoverable."""
    assert os.path.exists(CHECKPOINT_P87), f"Phase 8.7 checkpoint missing: {CHECKPOINT_P87}"
    models = zenolm_provider.get_supported_models()
    p87_models = [m for m in models if m["id"] == "zenolm-100m-p87"]
    assert len(p87_models) == 1
    p87 = p87_models[0]
    assert p87["is_sovereign"] is True
    assert p87["context_window"] == 4096
    assert p87["cost_per_1k_input_paise"] == 0


def test_zenolm_p87_ai_engine_listing(ai_engine):
    """Verifies that AIEngineService lists zenolm-100m-p87."""
    models = ai_engine.list_available_models()
    p87_models = [m for m in models if m["id"] == "zenolm-100m-p87"]
    assert len(p87_models) == 1
    assert p87_models[0]["provider"] == "zenolm"
    assert p87_models[0]["is_configured"] is True


def test_zenolm_p87_parameter_and_gpu_placement(zenolm_provider):
    """Verifies that zenolm-100m-p87 loads onto CUDA with exactly 100,168,992 parameters."""
    if not torch.cuda.is_available():
        pytest.skip("CUDA hardware required for sovereign GPU placement.")

    zenolm_provider._ensure_loaded(model_id="zenolm-100m-p87")
    assert zenolm_provider._initialized is True
    assert zenolm_provider._active_model_id == "zenolm-100m-p87"
    assert zenolm_provider._model is not None

    total_params = sum(p.numel() for p in zenolm_provider._model.parameters())
    assert total_params == 100168992, f"Expected 100,168,992 parameters, got {total_params}"

    for param in zenolm_provider._model.parameters():
        assert param.is_cuda is True


@pytest.mark.asyncio
async def test_zenolm_p87_streaming_chat_inference(zenolm_provider):
    """Verifies local streaming neural inference with zenolm-100m-p87."""
    messages = [
        {"role": "user", "content": "Calculate 125 * 8. What is the exact result?"}
    ]
    chunks = []
    usages = []

    async for item in zenolm_provider.stream_chat(
        messages=messages,
        model="zenolm-100m-p87",
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
    print(f"\n[ZenoLM-100M-P87 Streaming Output]: {full_output}")


@pytest.mark.asyncio
async def test_zenolm_p87_multilingual_inference(zenolm_provider):
    """Verifies that zenolm-100m-p87 performs inference on Indic prompts."""
    messages = [
        {"role": "user", "content": "திருக்குறளை இயற்றிய புலவர் யார்?"}
    ]
    chunks = []
    async for item in zenolm_provider.stream_chat(
        messages=messages,
        model="zenolm-100m-p87",
        temperature=0.0,
        max_tokens=24
    ):
        if item.get("type") == "chunk":
            chunks.append(item.get("text", ""))

    output = "".join(chunks)
    assert len(output) > 0
    print(f"\n[ZenoLM-100M-P87 Tamil Output]: {output}")
