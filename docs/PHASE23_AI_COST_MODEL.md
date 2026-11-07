# PHASE 23 — AI INFERENCE COST & CAPACITY MODEL

**Document Reference:** `ZYNOVA-DOC-PHASE23-AI-COST-MODEL`  
**Execution Timestamp:** 2026-11-07T10:03:00+05:30  
**Evaluator:** Principal Cloud Financial Operations (FinOps) Engineer  

---

## 1. FOUNDATIONAL PROVIDER PRICING MATRIX

Values converted to Indian Paise (100 Paise = ₹1.00 INR):

| Model Provider | Model Name | Context Window | Input Cost / 1k Tokens | Output Cost / 1k Tokens | Indic Token Efficiency |
| :--- | :--- | :---: | :---: | :---: | :---: |
| **Google Gemini** | `gemini-2.5-flash` | 1,000,000 | **10 Paise** (₹0.10) | **40 Paise** (₹0.40) | **95% (High)** |
| **Google Gemini** | `gemini-2.5-pro` | 2,000,000 | **150 Paise** (₹1.50) | **600 Paise** (₹6.00) | **95% (High)** |
| **OpenAI** | `gpt-4o-mini` | 128,000 | **15 Paise** (₹0.15) | **60 Paise** (₹0.60) | **85% (Moderate)** |
| **OpenAI** | `gpt-4o` | 128,000 | **250 Paise** (₹2.50) | **1000 Paise** (₹10.00)| **85% (Moderate)** |
| **Anthropic** | `claude-3-5-haiku` | 200,000 | **80 Paise** (₹0.80) | **400 Paise** (₹4.00) | **80% (Moderate)** |
| **Deterministic Mock** | `mock-indic-v1` | 4,096 | **0 Paise** (₹0.00) | **0 Paise** (₹0.00) | **100% (Free)** |

---

## 2. PRODUCTION COST PROJECTIONS

Assumptions:
- Standard consumer turn: 250 input tokens, 350 output tokens.
- Cost per standard turn using `gemini-2.5-flash`:
  - Input: `(250 / 1000) * 10 = 2.5 Paise`
  - Output: `(350 / 1000) * 40 = 14.0 Paise`
  - **Total per turn: 16.5 Paise (~₹0.17 INR)**

### Monthly User Volume Scenarios:
1. **Light User (30 turns/month):** `30 * ₹0.17 =` **₹5.10 / month**
2. **Standard User (150 turns/month):** `150 * ₹0.17 =` **₹25.50 / month**
3. **Power User (600 turns/month):** `600 * ₹0.17 =` **₹102.00 / month**

---

## 3. GUARDRAILS & COST CONTROLS

1. **Context Window Capping:** Context is pruned server-side to the 10 most recent message exchanges, preventing token explosion on long conversation threads.
2. **Turn Limits:** Default cap of 60 turns per hour per user account (`AI_MAX_TURNS_PER_HOUR`).
3. **Output Token Hard Cap:** Every API call enforces `maxOutputTokens=2048` to prevent runaway generation loops.
4. **Mock Fallback:** When external API keys are depleted or unconfigured, the engine seamlessly falls back to the deterministic local mock provider without crashing user interfaces.
