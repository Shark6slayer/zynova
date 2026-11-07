# PHASE 29 — AI CORE ENGINE PRODUCTION READINESS

## 1. Provider Abstraction Architecture
The Zynova AI Core Engine (`backend/app/services/ai_engine_service.py` & `ai_providers.py`) isolates client applications from LLM provider details, supporting:
- **Google Gemini API**: `gemini-2.5-flash`, `gemini-2.5-pro` (Default).
- **OpenAI API**: `gpt-4o`, `gpt-4o-mini`.
- **Anthropic API**: `claude-3-5-sonnet`.
- **Mock Provider**: Development and automated test harness only.

---

## 2. Production Safety Controls

### 2.1 Mock Mode Prohibition in Production
- In `production` environment, `AI_MOCK_MODE` is strictly disabled by default. If configured improperly, startup checks emit security alerts.
- Live inference requires valid provider API keys set via backend environment variables (`GEMINI_API_KEY`, etc.).

### 2.2 Token & Quota Protection
- **Input Quota**: Max 4,096 tokens per request.
- **Output Limit**: Max 2,048 tokens per turn.
- **Hourly Turn Limiting**: Capped at 60 turns per user/hour to avoid runaway API costs.
- **Inference Timeout**: Enforces 45.0s timeout per invocation.

### 2.3 Streaming & SSE Lifecycle
- Streaming responses emit formatted Server-Sent Events (`event: message\ndata: ...\n\n`).
- Client disconnects terminate backend generator loops immediately, avoiding wasted token consumption.
