# ZYNOVA 3.0 — PHASE 24: CONNECT PLATFORM ARCHITECTURE PLAN
**Document ID:** DOC-PHASE24-CONNECT-001  
**Author:** Principal Real-Time Systems & Messaging Engineer  
**Status:** Approved Technical Plan  
**Module:** Zynova Connect (WhatsApp-Inspired Experience)  

---

## 1. PRODUCT SPECIFICATION & VISION

**Zynova Connect** is an ultra-fast, privacy-first real-time messaging and calling application:
1. **Direct (1:1) Messaging**: Instant delivery, bidirectional typing indicators, real-time message state transitions (Sent `✓`, Delivered `✓✓`, Read `✓✓` blue).
2. **Group Chats**: Scalable group discussions up to 1,024 participants, custom group avatars, subject descriptions, admin roles, and invite links.
3. **Rich Media & Voice Notes**: Direct streaming voice notes with waveform rendering, photo/video sharing with preview blur hashes, and document transfers up to 50MB.
4. **Message Reactions & Replies**: Contextual swipe-to-reply quoting and emoji reaction arrays.
5. **Status Updates**: 24-hour disappearing text/image/video statuses with granular privacy selectors (Contacts only, Exclude specific users).
6. **WebRTC Voice & Video Calling**: High-definition peer-to-peer calling with camera toggling, screen sharing, and adaptive bitrate audio.
7. **Multi-Device Synchronization**: Independent device sessions synced seamlessly over WebSocket event streaming.

---

## 2. API ROUTE TAXONOMY & CONTRACTS

Prefix: `/api/v1/connect`

### 2.1 Conversations & Messages
- `GET /connect/conversations`: List active conversations sorted by `last_message.created_at`.
- `POST /connect/conversations`: Initiate 1:1 conversation or create group.
- `GET /connect/conversations/{conversation_id}/messages`: Fetch paginated chat history using cursor-based pagination (`before_id` or timestamp).
- `POST /connect/conversations/{conversation_id}/messages`: Send message (text, media attachment reference, or voice note).
- `DELETE /connect/messages/{message_id}`: Delete for everyone (within 1 hour) or delete for me.
- `POST /connect/messages/{message_id}/reactions`: Add or update emoji reaction.
- `POST /connect/messages/{message_id}/read`: Mark messages as read and emit receipt to sender.

### 2.2 Groups & Communities
- `PATCH /connect/conversations/{conversation_id}/group-info`: Update group name, icon, description.
- `POST /connect/conversations/{conversation_id}/members`: Add members (admin only).
- `DELETE /connect/conversations/{conversation_id}/members/{user_id}`: Remove member or leave group.
- `POST /connect/conversations/{conversation_id}/admins`: Grant/revoke admin privileges.

### 2.3 Status Updates (Stories)
- `POST /connect/status`: Post a 24-hour text or media status.
- `GET /connect/status/recent`: Retrieve status list from user's address book contacts.
- `POST /connect/status/{status_id}/view`: Register status view receipt.

### 2.4 Calls & Signaling (REST Endpoints)
- `POST /connect/calls/initiate`: Log call session and initiate WebRTC ring notification.
- `POST /connect/calls/{call_id}/terminate`: Log call duration and clean up session records.

---

## 3. MESSAGE STATE MACHINE & OFFLINE QUEUING

```
[Client Sends Message]
         │
         ▼
[Server Ingestion] ────► Status: "sent" (Single Check ✓)
         │
         ├─────────────────────────────────────────┐
         ▼                                         ▼
   [Recipient Online]                      [Recipient Offline]
   Delivered via WebSocket                 Buffered in MongoDB & Push via FCM/APNS
         │                                         │
         ▼                                         ▼
   Status: "delivered" (Double Check ✓✓)   (Client Reconnects)
         │                                 Pulls unread queue via sync
         ▼                                         │
   [Recipient Opens Conversation]                  ▼
   Status: "read" (Blue Double Check ✓✓) ◄─────────┘
```

### Offline Message Queue Guarantee:
When an offline recipient reconnects via WebSocket:
1. Client sends `client.sync { "last_received_sequence": 1042 }`.
2. Backend queries MongoDB `connect_messages` for all messages across user's conversations where `sequence > 1042`.
3. Messages are streamed in bulk chunks of 50, followed by a `sync.complete` event.
4. Client acknowledges receipt, triggering `delivered` status notifications back to respective senders.

---

## 4. DATABASE INTEGRATION & INDEXING HIGHLIGHTS

References schemas in `docs/PHASE24_DATABASE_ARCHITECTURE.md`:
- `connect_conversations`: Compound index on `[("participants.user_id", 1), ("last_message.created_at", -1)]` guarantees instantaneous conversation inbox rendering.
- `connect_messages`: Compound index on `[("conversation_id", 1), ("created_at", -1)]` enables high-speed cursor pagination for endless scroll chat histories.
- `user_devices`: Tracks multi-device push tokens (FCM/APNS) and public Signal protocol identity keys.
