# PHASE 23 — AI CORE ARCHITECTURE & PROVIDER ABSTRACTION

**Document Reference:** `ZYNOVA-DOC-PHASE23-AI-CORE-ARCH`  
**Execution Timestamp:** 2026-11-07T10:00:00+05:30  
**Evaluator:** Principal AI Architect & AI Infrastructure Engineer  

---

## 1. ARCHITECTURAL TOPOLOGY

The Zynova AI Core Engine implements a clean decoupled architecture separating client applications from upstream foundational model APIs.

```
┌────────────────────────────────────────────────────────┐
│                   CLIENT APPLICATIONS                  │
│       - React 19 Web App (`AIAssistantView.tsx`)        │
│       - Capacitor Android Mobile Native Client         │
└───────────────────────────┬────────────────────────────┘
                            │
                            │ 1. EventStream POST /api/v1/ai/chat/stream
                            │    (Bearer JWT + Locale Header)
                            ▼
┌────────────────────────────────────────────────────────┐
│               ZYNOVA FASTAPI SOVEREIGN BACKEND         │
│                                                        │
│  ┌──────────────────┐           ┌───────────────────┐  │
│  │ Auth & Boundary  │           │   Audit Ledger    │  │
│  │ User Isolation   │           │   (Ed25519 Chain) │  │
│  └────────┬─────────┘           └─────────▲─────────┘  │
│           │                               │            │
│           ▼                               │ 2. Audit   │
│  ┌────────────────────────────────────────┴─────────┐  │
│  │            AIEngineService Orchestrator          │  │
│  │   - Dynamic Context Pruning (Recent 10 turns)    │  │
│  │   - Sovereign Indic System Instruction Prompt    │  │
│  │   - Safe Fallback to Deterministic Mock          │  │
│  └────────────────────────┬─────────────────────────┘  │
└───────────────────────────┼────────────────────────────┘
                            │
                            │ 3. Asynchronous Token Streaming
                            ▼
┌────────────────────────────────────────────────────────┐
│                PROVIDER ABSTRACTION LAYER              │
│                                                        │
│   ┌────────────────────────────────────────────────┐   │
│   │ BaseAIProvider Abstract Contract               │   │
│   └───────┬──────────────┬──────────────┬──────────┘   │
│           │              │              │              │
│           ▼              ▼              ▼              │
│    ┌────────────┐ ┌────────────┐ ┌────────────┐        │
│    │  Gemini    │ │   OpenAI   │ │ Anthropic  │        │
│    │  Provider  │ │  Provider  │ │  Provider  │        │
│    └────────────┘ └────────────┘ └────────────┘        │
│           │              │              │              │
│           └──────────────┼──────────────┘              │
│                          ▼ Fallback                    │
│                   ┌────────────┐                       │
│                   │   Mock     │                       │
│                   │  Provider  │                       │
│                   └────────────┘                       │
└────────────────────────────────────────────────────────┘
```

---

## 2. CORE SYSTEM COMPONENTS

### 1. `BaseAIProvider` (`backend/app/services/ai_providers.py`)
- Standardized async generator interface `stream_chat(...)`.
- Decouples proprietary API payloads from client-facing Server-Sent Events (SSE).
- Guarantees zero secret leakage: API keys are loaded strictly from server-side environment variables and never exposed to the frontend.

### 2. Supported Foundational Providers
1. **Google Gemini (`GeminiProvider`):**
   - Direct HTTP SSE connection to `v1beta/models/{model}:streamGenerateContent`.
   - Native support for `gemini-2.5-flash` and `gemini-2.5-pro`.
   - Optimized for low latency and native tokenization of 22 Indian scheduled languages.
2. **OpenAI (`OpenAIProvider`):**
   - Connects to `/v1/chat/completions` supporting `gpt-4o` and `gpt-4o-mini`.
3. **Anthropic (`AnthropicProvider`):**
   - Connects to `/v1/messages` supporting `claude-3-5-sonnet` and `claude-3-5-haiku`.
4. **Deterministic Mock (`MockAIProvider`):**
   - Always enabled and configured for CI/CD test suites and local sandboxing.
   - Generates realistic multilingual tokens without network requests or billing costs.

### 3. Server-Sent Events (SSE) Protocol
The client establishes an HTTP POST streaming connection to `/api/v1/ai/chat/stream`:
```http
POST /api/v1/ai/chat/stream HTTP/1.1
Host: zynova-backend-dgpe.onrender.com
Authorization: Bearer <JWT_ACCESS_TOKEN>
Content-Type: application/json

{
  "prompt": "வணக்கம் Zynova, explain quantum entanglement in Tanglish",
  "provider": "gemini",
  "model": "gemini-2.5-flash",
  "locale": "ta"
}
```
**Streamed SSE Response Frames:**
```text
data: {"type": "start", "conversation_id": "ai_conv_9a8f2c", "model": "gemini-2.5-flash", "provider": "gemini"}

data: {"type": "chunk", "text": "Vanakkam! "}

data: {"type": "chunk", "text": "Quantum entanglement na "}

data: {"type": "chunk", "text": "two particles connected-aa irukkum..."}

data: {"type": "done", "full_length": 842}
```
