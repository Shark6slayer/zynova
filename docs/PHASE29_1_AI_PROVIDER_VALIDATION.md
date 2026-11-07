# PHASE 29.1 — AI PROVIDER ACTIVATION & CREDENTIAL MATRIX

## 1. Provider Status Audit

| Provider | Supported Models | Credential Required | Active Credential | Live State |
| :--- | :--- | :--- | :--- | :--- |
| **Google Gemini** | `gemini-2.5-flash`, `gemini-2.5-pro` | `GEMINI_API_KEY` | *Not Configured* | **Awaiting Staging Key** |
| **OpenAI** | `gpt-4o`, `gpt-4o-mini` | `OPENAI_API_KEY` | *Not Configured* | **Awaiting Staging Key** |
| **Anthropic** | `claude-3-5-sonnet` | `ANTHROPIC_API_KEY` | *Not Configured* | **Awaiting Staging Key** |
| **Mock Provider** | `mock-echo-model` | None (Test only) | N/A | **Restricted to dev/test** |

---

## 2. Safe Error Handling & Rejection Verification
- **Rejection Behavior**: When an API key is missing, providers reject requests at runtime with a clean, typed `AIProviderException(AIErrorCode.AUTHENTICATION_ERROR)`.
- **Zero Leakage**: No raw HTTP client errors, stack traces, or internal URLs leak to clients.
- **Mock-Mode Guard**: `AI_MOCK_MODE` remains `false` in production/staging to ensure mock inference never silently masquerades as live intelligence.

---

## 3. Operator Activation Guide

To activate live AI inference on staging/production, provision the following environment variables in the Render / hosting console:

```bash
# Set primary AI provider
AI_DEFAULT_PROVIDER="gemini"
AI_DEFAULT_MODEL="gemini-2.5-flash"

# Provide at least one valid key:
GEMINI_API_KEY="AIzaSy..."
# Optional fallbacks:
OPENAI_API_KEY="sk-..."
ANTHROPIC_API_KEY="sk-ant-..."
```
