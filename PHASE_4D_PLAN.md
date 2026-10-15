# SUPER_AI Phase 4D: Real-Time User Messaging Implementation Plan

## 1. Objectives & Scope
- Deliver secure, human-to-human real-time messaging between authenticated users.
- Isolate human messaging from the AI Copilot conversation engine.
- Provide full REST API: user search, conversation initiation/retrieval, message history with pagination, sending, editing, deleting, marking as read, unread counts.
- Real-time communication via FastAPI WebSockets with token authentication, room authorization, real-time dispatch, and client resync.
- Comprehensive React chat UI in `src/features/chat/ChatModuleView.tsx` with conversation sidebar, user search modal, optimistic message sending, unread badges, timestamps, read receipts, and edit/delete actions.
- Multi-user automated integration tests verifying security isolation, pagination, editing/deleting, unread counts, and real-time WebSocket messaging.

## 2. Data Models
- **`chat_rooms` (collection)**:
  - `_id`: ObjectId
  - `type`: "direct" (extensible to "group")
  - `participants`: `[user_id_1, user_id_2]`
  - `participant_meta`: `{ user_id: { username, full_name, avatar_url } }`
  - `last_message`: `{ id, sender_id, text, created_at }`
  - `unread_counts`: `{ user_id: int }`
  - `created_at`: datetime
  - `updated_at`: datetime
- **`chat_messages` (collection)**:
  - `_id`: ObjectId
  - `conversation_id`: str
  - `sender_id`: str (derived from JWT, never client input)
  - `sender_username`: str
  - `sender_full_name`: str
  - `sender_avatar`: Optional[str]
  - `text`: str (max 2000 chars)
  - `created_at`: datetime
  - `updated_at`: datetime
  - `is_edited`: bool
  - `is_deleted`: bool
  - `read_by`: `[user_id_1, ...]`

## 3. Endpoints & Real-Time Flow
- `GET /api/v1/chat/users/search?q=...`
- `POST /api/v1/chat/conversations` (Get or create 1-to-1 conversation)
- `GET /api/v1/chat/conversations` (List user's active conversations)
- `GET /api/v1/chat/conversations/{conv_id}/messages?limit=30&before=...` (Paginated history)
- `POST /api/v1/chat/conversations/{conv_id}/messages` (Send message)
- `PATCH /api/v1/chat/messages/{msg_id}` (Edit own message)
- `DELETE /api/v1/chat/messages/{msg_id}` (Soft delete own message)
- `POST /api/v1/chat/conversations/{conv_id}/read` (Mark conversation read)
- `GET /api/v1/chat/unread-count` (Total unread count for user)
- `WebSocket /api/v1/chat/ws?token=...` (Authenticated WebSocket with room subscription and live dispatch)
