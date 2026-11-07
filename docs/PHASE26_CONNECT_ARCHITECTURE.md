# ZYNOVA CONNECT — PHASE 26 ARCHITECTURE SPECIFICATION
**WhatsApp-Inspired Real-Time Communication Platform Architecture**  
**Repository:** `C:\super_ai`  
**Base Target:** `feature/phase-26-zynova-connect`  
**Version:** 3.0.0-PROD  

---

## 1. System Topology & Core Components

Zynova Connect provides sovereign, end-to-end encrypted peer-to-peer and group communications.

```
       [ Client Applications (Web & Capacitor Android) ]
                    │                        │
       (WSS WebSocket Gateway)       (HTTPS REST API)
                    │                        │
  ┌─────────────────▼────────────────────────▼──────────────────┐
  │                   Zynova Connect Engine                     │
  │  - Real-time Connection Manager (Active WS + Last Seen)     │
  │  - Double Ratchet E2EE Subsystem (X25519, HKDF, AES-256)    │
  │  - Group & Community Hierarchy Orchestrator                 │
  │  - Ephemeral Status & Media Pipeline (24h TTL)              │
  │  - WebRTC ICE/STUN/TURN Signaling Broker                    │
  │  - Argon2id Locked Chat Protected Vault                     │
  └─────────────────┬────────────────────────┬──────────────────┘
                    │                        │
          (MongoDB Collections)      (KMS Envelope Encryption)
```

---

## 2. Platform Domain Models

1. **Conversations (`chat_rooms`):**
   - Supports `type: "direct"` (1-to-1) and `type: "group"`.
   - Dynamic `admin_ids` role assignment.
   - Per-user `archived_by` and `locked_by` (Argon2id hashed PINs).
   - Real-time `pinned_message_id`.

2. **Messages (`chat_messages`):**
   - Delivery statuses: `sent` ➔ `delivered` ➔ `read`.
   - Multi-format media support: text, voice, audio, images, videos, documents.
   - In-place editing (`is_edited: true`) and soft-delete (`is_deleted: true`).
   - Interactive reactions (`reactions: {user_id: emoji}`).
   - Client idempotency with `client_message_id`.

3. **Status Updates (`connect_statuses`):**
   - 24-hour UTC expiration with native TTL.
   - Media cards, text-with-background styles, and read receipts.

4. **Communities (`connect_communities`):**
   - Multi-group umbrella containers with unified announcement broadcast channels.

5. **WebRTC Calling (`connect_calls`):**
   - Voice and video call signaling over WebSocket with session duration logging.
