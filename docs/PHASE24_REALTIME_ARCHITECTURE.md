# ZYNOVA 3.0 — PHASE 24: REAL-TIME ARCHITECTURE & SIGNALING SPECIFICATION
**Document ID:** DOC-PHASE24-REALTIME-001  
**Author:** Principal Real-Time Communication & Distributed Systems Engineer  
**Status:** Approved Architecture Specification  
**Scope:** WebSockets, Redis Pub/Sub Backplane, WebRTC Signaling, and Presence Tracking  

---

## 1. EXECUTIVE SUMMARY

Zynova's expansion requires real-time capabilities across all three platforms:
- **Zynova Connect**: Sub-100ms message delivery, typing indicators, read receipts, active presence (online/last seen), and 1:1 / group WebRTC voice and video calling.
- **Zynova Social**: Instant notification dispatch (likes, comments, new followers), live story view updates, and real-time reel comments.
- **Zynova Video**: Live stream chat rooms, viewer count synchronization, and creator stream status changes.

To evolve from the existing single-node in-memory `ws_manager.py` into a resilient, horizontally scalable real-time engine, Zynova introduces a **Redis Pub/Sub Backplane** coupled with an authenticated WebSocket protocol and WebRTC signaling exchange.

---

## 2. REAL-TIME TOPOLOGY & DISTRIBUTED PUBSUB BACKPLANE

In multi-instance production environments (e.g. Render, Kubernetes, Docker Swarm), clients connected to different backend instances must exchange events transparently.

```
       [ Client A (User 101) ]           [ Client B (User 202) ]
                  │                                  │
                  ▼                                  ▼
      [ FastAPI Instance 1 ]             [ FastAPI Instance 2 ]
      (In-Memory ws_manager)             (In-Memory ws_manager)
                  │                                  │
                  └────────► [ Redis Cluster ] ◄─────┘
                            Pub/Sub Backplane
                     Channels:
                     - user:202:inbox
                     - conversation:conv_abc:events
                     - video:live_xyz:chat
```

### 2.1 Redis Channel Partitioning
1. **Direct User Inboxes**: `zynova:user:{user_id}:events`
   - Delivers new private messages, call offers, read receipts, and system alerts to all active devices of `{user_id}`.
2. **Conversation Channels**: `zynova:conv:{conversation_id}:events`
   - Broadcasts typing indicators, member join/leave, and group metadata updates.
3. **Live Stream Rooms**: `zynova:video:{video_id}:chat`
   - Broadcasts live viewer comments and high-frequency reactions with rate-limited burst buffers.
4. **Global Presence Broadcast**: `zynova:presence:heartbeat`
   - Used by workers to monitor connection heartbeats and broadcast online/offline transitions.

---

## 3. WEBSOCKET CONNECTION LIFECYCLE & PROTOCOL

### 3.1 Handshake & Authentication
WebSockets connect over `wss://zynova.intellidev.in/api/v1/ws`.
- **Authentication**: JWT access token passed via query parameter `?token=<JWT>` or during the initial `connection_init` frame.
- **Client Heartbeat**: The client sends a `ping` packet every 25 seconds; the server responds with `pong`. Connections without ping/pong within 60 seconds are terminated to release file descriptors.

### 3.2 Standard Frame Envelope Specification
All WebSocket messages exchanged adhere to the following JSON structure:

```json
{
  "type": "chat.message.new | chat.typing | webrtc.signal | notification.push | presence.update",
  "id": "evt_98f4b1a0e234",
  "timestamp": "2026-11-07T10:45:00.000Z",
  "payload": {}
}
```

---

## 4. WEBRTC SIGNALING SPECIFICATION (CONNECT CALLS)

WebRTC enables direct peer-to-peer audio and video communication, avoiding backend bandwidth consumption. The FastAPI server acts purely as the signaling bridge to exchange SDP (Session Description Protocol) offers, answers, and ICE (Interactive Connectivity Establishment) candidates.

### 4.1 Signaling Flow Sequence

```mermaid
sequenceDiagram
    autonumber
    actor Caller as User A (Caller)
    participant WS_A as Server (WS A)
    participant Redis as Redis Backplane
    participant WS_B as Server (WS B)
    actor Callee as User B (Callee)

    Caller->>WS_A: send {"type": "webrtc.call_init", "callee_id": "B", "call_type": "video"}
    WS_A->>Redis: PUBLISH user:B:events (type="webrtc.incoming_call", call_id, sdp_offer)
    Redis->>WS_B: Message forwarded
    WS_B->>Callee: deliver {"type": "webrtc.incoming_call", "call_id": "call_123", "caller": "A"}

    Callee->>WS_B: send {"type": "webrtc.call_accept", "call_id": "call_123", "sdp_answer": "..."}
    WS_B->>Redis: PUBLISH user:A:events (type="webrtc.call_accepted", sdp_answer)
    Redis->>WS_A: Message forwarded
    WS_A->>Caller: deliver {"type": "webrtc.call_accepted", "sdp_answer": "..."}

    par ICE Candidate Exchange
        Caller->>WS_A: send {"type": "webrtc.ice_candidate", "candidate": {...}}
        WS_A->>Redis->>WS_B->>Callee: deliver ICE candidate
    and
        Callee->>WS_B: send {"type": "webrtc.ice_candidate", "candidate": {...}}
        WS_B->>Redis->>WS_A->>Caller: deliver ICE candidate
    end

    Note over Caller, Callee: P2P Encrypted WebRTC Audio/Video Stream Established
```

### 4.2 WebRTC Signaling Event Types
1. `webrtc.call_init`: Initiates a call with initial SDP Offer and caller capabilities.
2. `webrtc.incoming_call`: Delivered to callee device(s) with ringtone trigger payload.
3. `webrtc.call_accept`: Callee accepts call and returns SDP Answer.
4. `webrtc.call_reject`: Callee declines or busy with another call.
5. `webrtc.ice_candidate`: Transports ICE network candidates (STUN/TURN network interfaces).
6. `webrtc.call_end`: Terminates call session and closes peer connections.

### 4.3 NAT Traversal: STUN & TURN Infrastructure
- **STUN (Session Traversal Utilities for NAT)**: Google / Cloudflare public STUN servers resolve public IP/port mappings.
- **TURN (Traversal Using Relays around NAT)**: Self-hosted Coturn or Twilio/Cloudflare TURN relay with time-limited ephemeral credentials generated via HMAC-SHA1 for clients behind symmetric NAT or corporate firewalls.

---

## 5. PRESENCE TRACKING & TYPING INDICATORS

### 5.1 Presence Architecture
- **Online State**: Stored in Redis Sorted Sets / Hashes with TTL:
  - Key: `zynova:presence:user:{user_id}` -> `{"status": "online", "last_seen": <epoch>, "device_count": 2}`
  - Heartbeat: Each connected client refreshes the Redis key TTL (set to 60s) every 30s.
  - Disconnect: When all WebSocket connections for a user terminate, status flips to `offline` and `last_seen` timestamp is committed to MongoDB `users` collection.
- **Privacy Controls**: Users can configure `last_seen_privacy` (`"everyone"`, `"contacts"`, `"nobody"`). The server checks reciprocal privacy settings before delivering presence payloads.

### 5.2 Ephemeral Typing Indicators
- Typing indicators bypass persistent databases entirely.
- Sent via WebSocket: `{"type": "chat.typing", "conversation_id": "conv_123", "is_typing": true}`.
- Broadcast to other conversation participants via Redis pub/sub with an automatic client-side 3-second debounce.
