# PHASE 23.1 — COST AND TOKEN ACCOUNTING REPORT

**Document Reference:** `ZYNOVA-DOC-PHASE23-1-COST-VALIDATION`  
**Execution Timestamp:** 2026-11-07T10:18:00+05:30  
**Evaluator:** Cloud FinOps & Analytics Lead  

---

## 1. EMPIRICAL TOKEN CAPTURE ARCHITECTURE

- When streaming completions from upstream providers:
  - **Gemini:** Reads `usageMetadata.promptTokenCount` and `candidatesTokenCount`.
  - **OpenAI:** Reads `stream_options.include_usage` telemetry (`prompt_tokens`, `completion_tokens`).
  - **Anthropic:** Reads `message_start` block telemetry (`input_tokens`, `output_tokens`).
  - **Mock Sandbox:** Estimates tokens based on word count chunks and explicitly flags `is_estimated: True`.
- Token metrics are delivered to the frontend via `data: {"type": "usage", "tokens_in": ..., "tokens_out": ...}` frames.
- Cumulative metrics are incremented atomically in MongoDB on the parent conversation document:
  ```python
  "$inc": {
      "total_tokens_in": tokens_in or 0,
      "total_tokens_out": tokens_out or 0
  }
  ```

---

## 2. PRODUCTION QUOTAS & BUDGET BOUNDARIES

Configured in `backend/app/core/config.py`:
- `AI_MAX_INPUT_TOKENS`: **4,096 tokens** per prompt.
- `AI_MAX_OUTPUT_TOKENS`: **2,048 tokens** per turn.
- `AI_MAX_TURNS_PER_HOUR`: **60 turns** per authenticated user.
- `AI_INFERENCE_TIMEOUT_SECONDS`: **45.0s** hard connection ceiling.
