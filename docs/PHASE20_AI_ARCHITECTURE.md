# PHASE 20 — AI INFRASTRUCTURE AND INFERENCE ARCHITECTURE

**Document Reference:** `ZYNOVA-DOC-PHASE20-AI`  
**Execution Timestamp:** 2026-11-07T09:51:30+05:30  
**Evaluator:** Principal AI Engineer & Distributed Systems Lead  

---

## 1. REPOSITORY AUDIT OF EXISTING AI IMPLEMENTATIONS

- **Frontend (`AIAssistantView.tsx`):**
  - Implements multi-model selector (`SUPER Multilingual Indic-v2`, `Indic-LLM-Pro`).
  - Displays prompt topology, memory schemas, and execution cards.
  - Flags `isAIEngineConfigured = false` with transparent notice:
    > *"AI service unavailable: No active LLM provider or self-hosted model endpoint is connected to this deployment. Real-time inference cannot be performed."*
- **Backend (`backend/`):**
  - Zero external LLM client SDKs (`google-genai`, `openai`, `anthropic`) exist in `backend/requirements.txt`.
  - No active inference routes or token streaming endpoints are declared under `/api/v1/`.
  - **Verdict:** Honest UI presentation. Zero active background LLM inference is currently connected.

---

## 2. PRODUCTION MULTILINGUAL AI INTEGRATION ARCHITECTURE

```
┌──────────────┐          1. Streaming Chat / Prompt         ┌─────────────────────────┐
│              ├────────────────────────────────────────────►│  Zynova FastAPI Backend │
│              │◄────────────────────────────────────────────┤  (WebSocket or SSE)     │
│              │          4. Token-by-Token Stream           └────────────┬────────────┘
│  Zynova Web  │                                                          │
│  / Mobile UI │                                                          │ 2. Context Aggregation
│              │                                                          ▼
│              │                                             ┌─────────────────────────┐
│              │                                             │ MongoDB `conversations` │
│              │                                             │ & User Locale Prefs     │
│              │                                             └────────────┬────────────┘
│              │                                                          │
│              │                                                          │ 3. Gemini Streaming
│              │                                                          ▼
│              │                                             ┌─────────────────────────┐
│              │                                             │ Google Gemini API       │
│              │                                             │ `gemini-2.5-flash`      │
│              │                                             │ (Indic Multilingual)    │
│              │                                             └─────────────────────────┘
```

---

## 3. CORE DESIGN DECISIONS

1. **Model Selection:**
   - Primary: **Gemini 2.5 Flash / 3.8 Flash** via `google-genai` SDK.
   - Rationale: High inference speed (<250ms time-to-first-token), native tokenization efficiency across all 22 scheduled Indian languages, and cost-effective pricing for consumer traffic.
2. **Streaming Protocol:**
   - Implement **Server-Sent Events (SSE)** via `StreamingResponse` on `POST /api/v1/ai/chat/stream`.
   - Native fallback to WebSocket on existing `ws_manager.py` if bidirectional interaction is needed.
3. **Context Management & Storage:**
   - Retain sliding window of past 10 message exchanges in MongoDB `conversations` collection.
   - Inject verified user language preferences from `preferences.py` to enforce language coherence without requiring the user to specify their language repeatedly.
4. **Rate Limiting & Safety Boundaries:**
   - Tiered token buckets per user ID (e.g., 60 prompt turns per hour for standard accounts).
   - Server-side moderation filter prevents prompt injection and sensitive credential extraction.

