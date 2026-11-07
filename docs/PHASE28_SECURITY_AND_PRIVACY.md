# PHASE 28 — SECURITY, PRIVACY & ACCESS CONTROL SPECIFICATION

## 1. Multi-Platform Security Controls

### 1.1 Cross-Platform Mutual Blocking
Blocking is enforced bidirectionally at the database query layer:
- **Search**: `users.blocked_users` exclusions hide blocked users, posts, videos, and channels from results.
- **Messaging**: Initiating a direct message to a blocked contact yields `403 Forbidden`.
- **Social Graph**: Follow requests between blocked accounts are automatically rejected.
- **Video & Channels**: Subscribing to or commenting on a blocked creator's content is blocked.
- **Share Links**: Resolving `/api/v1/platform/share/*` returns `403 Forbidden` if either the caller or author is blocked.

### 1.2 Broken Object Level Authorization (BOLA) Mitigations
- **Private Content Gate**: Private videos and restricted chats check ownership/membership before reading filesystem blocks or returning JSON payloads.
- **Notification Privacy**: Notifications respect `preview_privacy` preferences (`full`, `sender_only`, `hidden`), preventing sensitive chat snippets from leaking onto lock screens or unauthenticated views.

### 1.3 Session Revocation
- Password resets, suspensions, and manual session termination set `tokens_revoked_before = now()`.
- JWT middleware validates `iat >= tokens_revoked_before`.
