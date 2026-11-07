# PHASE 23 — AI CORE IMPLEMENTATION SPECIFICATION

**Document Reference:** `ZYNOVA-DOC-PHASE23-AI-IMPL`  
**Execution Timestamp:** 2026-11-07T10:01:30+05:30  
**Evaluator:** Senior Backend Engineer & Full-Stack Developer  

---

## 1. BACKEND ROUTE & SERVICE SPECIFICATIONS

### Controller: `backend/app/api/routes/ai.py`
Mounted at `/api/v1/ai/`:

| Method | Endpoint | Auth Required | Description |
| :--- | :--- | :---: | :--- |
| `GET` | `/models` | No | Lists supported AI providers, models, context limits, and configuration status. |
| `GET` | `/conversations` | Yes | Retrieves user's active conversation threads sorted by latest update. |
| `GET` | `/conversations/{id}` | Yes | Retrieves full message history for a specific conversation thread. Strictly isolated to owner. |
| `DELETE`| `/conversations/{id}` | Yes | Deletes a conversation thread and its associated messages. |
| `POST` | `/chat/stream` | Yes | Initiates SSE real-time token streaming inference. |

---

## 2. CONVERSATION PERSISTENCE DATA SCHEMA

Persisted in MongoDB collection: `ai_conversations`

```json
{
  "_id": "6724fa...",
  "id": "ai_conv_7a8bc92d1",
  "user_id": "670c3e981...",
  "title": "Quantum entanglement in Tanglish",
  "created_at": "2026-11-07T10:00:00Z",
  "updated_at": "2026-11-07T10:00:15Z",
  "message_count": 2,
  "total_tokens_consumed": 215,
  "is_archived": false,
  "messages": [
    {
      "id": "msg_4891a",
      "role": "user",
      "content": "Vanakkam Zynova, explain quantum physics in Tanglish",
      "created_at": "2026-11-07T10:00:00Z"
    },
    {
      "id": "msg_4891b",
      "role": "assistant",
      "content": "Vanakkam! Quantum physics na atomic scale-la...",
      "model_used": "gemini-2.5-flash",
      "created_at": "2026-11-07T10:00:15Z"
    }
  ]
}
```

---

## 3. FRONTEND UPGRADE (`AIAssistantView.tsx`)

The upgraded view delivers:
- **Live Model Selection:** Dynamic dropdown populated from `/api/v1/ai/models`.
- **Sidebar Conversation List:** Displays all user threads, message counts, and one-click deletion.
- **AbortController Stop Generation:** Allows users to halt long-running generation midway (`handleStopGeneration`).
- **Markdown & Code Rendering:** Clean typography with copy-to-clipboard functionality.
- **Indic Locale Badge:** Syncs with active user preferences (`preferences?.language`).
