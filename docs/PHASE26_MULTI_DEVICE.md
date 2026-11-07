# ZYNOVA CONNECT — MULTI-DEVICE & SESSION SYNCHRONIZATION
**Linked Devices, Browser Sessions, and Cross-Device State Consistency**  

---

## 1. Device Registration & Verification

- Connect accounts support up to 5 concurrent linked companion devices.
- Devices are registered via `POST /api/v1/devices/register` with public key verification.
- Session tokens are strictly partitioned with distinct JTIs and device fingerprints; tokens are never logged or exposed via query parameters.

---

## 2. Multi-Device Message Synchronization

When a message is broadcast:
- The WebSocket manager maps active WebSocket connections per `user_id`.
- If an account has multiple active clients (e.g. Android phone + Web browser), all connected clients receive the real-time payload.
- Read receipts emitted from one client trigger `conversation_read` broadcast, resetting unread counts across all active companion devices.

---

## 3. Remote Session Revocation

Users can inspect active sessions via `GET /api/v1/devices/sessions` and selectively revoke companion devices via `DELETE /api/v1/devices/sessions/{id}`. Revoked tokens are immediately added to the blacklisted token registry.
