# ZYNOVA CONNECT — MESSAGING & DELIVERY ENGINE
**Real-Time Delivery Lifecycle, Receipts, Offline Queues & Synchronization**  

---

## 1. Message Delivery States

Zynova Connect enforces strict message lifecycle states:
- **`sent`**: The message has reached the backend cluster, validated against rate limits, encrypted at rest, and assigned an ID and sequence timestamp.
- **`delivered`**: At least one recipient active WebSocket client received the real-time push frame.
- **`read`**: The conversation was opened or marked read by the recipient (`/conversations/{id}/read`).

---

## 2. Idempotency & Duplicate Prevention

To withstand poor network conditions and mobile reconnect loops:
- Clients submit a UUID `client_message_id`.
- The database enforces uniqueness on `{"conversation_id": 1, "client_message_id": 1}`.
- Re-transmissions return the existing recorded message without duplicating notifications or unread counts.

---

## 3. Real-Time WebSocket Gateway Protocol

### Client to Server:
- `ping`: Keepalive heartbeat; server replies `pong`.
- `{"type": "typing", "conversation_id": "<id>"}`: Transmits ephemeral typing indicator to participants.

### Server to Client Events:
- `new_message`: Incoming message frame.
- `message_edited`: Real-time text update.
- `message_deleted`: Real-time tombstone.
- `message_reaction`: Emoji reaction updates.
- `message_pinned`: New pinned message anchor.
- `conversation_read`: Real-time read receipt updates.
