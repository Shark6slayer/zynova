import os
import sys
import asyncio
from typing import Dict, Any

from app.services.ai_providers import GeminiProvider, OpenAIProvider, AnthropicProvider
from app.core.ai_errors import AIProviderException

def build_smoke_status_matrix() -> Dict[str, Dict[str, Any]]:
    """
    Evaluates provider configuration, credentials presence, and live readiness.
    Smoke tests are explicitly opt-in via RUN_LIVE_AI_SMOKE=true.
    Never prints credentials.
    """
    providers = {
        "gemini": {
            "name": "Google Gemini",
            "provider": GeminiProvider(api_key=os.getenv("GEMINI_API_KEY")),
            "env_key": "GEMINI_API_KEY",
            "test_model": "gemini-2.5-flash"
        },
        "openai": {
            "name": "OpenAI",
            "provider": OpenAIProvider(api_key=os.getenv("OPENAI_API_KEY")),
            "env_key": "OPENAI_API_KEY",
            "test_model": "gpt-4o-mini"
        },
        "anthropic": {
            "name": "Anthropic Claude",
            "provider": AnthropicProvider(api_key=os.getenv("ANTHROPIC_API_KEY")),
            "env_key": "ANTHROPIC_API_KEY",
            "test_model": "claude-3-5-haiku-latest"
        }
    }

    run_live = os.getenv("RUN_LIVE_AI_SMOKE", "false").lower() == "true"
    matrix = {}

    for pid, pdata in providers.items():
        prov = pdata["provider"]
        is_conf = prov.is_configured()
        
        status = "IMPLEMENTED"
        if is_conf:
            status = "CONFIGURED"
            if run_live:
                status = "NOT TESTED"
            else:
                status = "CONFIGURED (OPT-IN RUNNER NOT SET)"
        else:
            status = "NOT CONFIGURED (API KEY MISSING)"

        matrix[pid] = {
            "display_name": pdata["name"],
            "model": pdata["test_model"],
            "configured": is_conf,
            "status": status,
            "live_tested": False
        }

    return matrix

async def run_opt_in_live_smoke():
    matrix = build_smoke_status_matrix()
    print("=== ZYNOVA AI PROVIDER SMOKE STATUS MATRIX ===")
    for pid, info in matrix.items():
        print(f"[{pid.upper()}] {info['display_name']} -> Status: {info['status']} (Model: {info['model']})")

if __name__ == "__main__":
    asyncio.run(run_opt_in_live_smoke())
