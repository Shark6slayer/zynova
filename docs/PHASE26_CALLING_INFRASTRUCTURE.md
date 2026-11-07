# ZYNOVA CONNECT — WEBRTC CALLING INFRASTRUCTURE
**P2P Voice & Video Calling, Signaling Gateway, and Call Logging**  

---

## 1. WebRTC Signaling Protocol

Zynova Connect leverages authenticated WebSockets for real-time SDP and ICE candidate negotiation:

```
[ Caller ]                          [ Zynova WS Gateway ]                         [ Callee ]
     │                                        │                                       │
     ├── 1. POST /calls/initiate ────────────►│                                       │
     │                                        ├── 2. incoming_call (WS) ─────────────►│
     │                                        │                                       │
     │◄── 3. call_signal: offer (WS) ─────────┴──────── 4. POST /calls/signal (offer) ┤
     │                                        │                                       │
     ├── 5. POST /calls/signal (answer) ─────►├── 6. call_signal: answer (WS) ───────►│
     │                                        │                                       │
     │◄── 7. ICE Candidates (WS) ─────────────┴──────── 8. ICE Candidates (WS) ──────►│
     │                                                                                │
     ▼══════════════════ [ Direct Encrypted SRTP Peer Connection ] ═══════════════════▼
```

---

## 2. STUN / TURN Server Configuration

- **STUN**: Resolves client NAT public IP addresses (`stun:stun.l.google.com:19302`).
- **TURN**: Relays media traffic across symmetric NATs or restrictive corporate firewalls.
- **Production Calling Notice**: P2P direct calling works across typical NATs; global enterprise-grade calling requires deployed TURN relay credentials.
