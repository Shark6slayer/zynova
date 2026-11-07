# PHASE 28 — UNIFIED NOTIFICATION CENTRE SPECIFICATION

## 1. Overview
The Notification Centre (`/api/v1/notifications`) provides a real-time activity stream for all platform interactions, featuring category filtering, read state management, and user notification preferences.

---

## 2. Notification Taxonomy

| Category | Event Types | Generated Scenarios | Navigation Target |
| :--- | :--- | :--- | :--- |
| `social` | `social_like`, `social_comment`, `social_follow` | Post likes, threaded replies, follower requests | `/post/{id}`, `/profile/{id}` |
| `connect` | `connect_message`, `connect_call`, `group_invite`| New 1:1 message, missed voice/video call | `/chat/{conv_id}` |
| `video` | `video_subscription`, `video_upload`, `video_comment`| New subscriber, creator upload, video comment | `/videos/{id}`, `/channel/{handle}` |
| `system` | `security_alert`, `device_session` | New login from unrecognized device, password change | `/settings` |

---

## 3. Privacy & Preview Controls
Users configure notification preferences via `GET/PATCH /api/v1/notifications/preferences`:
- `social_likes`, `social_comments`, `social_follows`: Boolean toggles.
- `connect_messages`, `connect_calls`: Messaging alert toggles.
- `video_subscriptions`, `video_uploads`: Creator alerts.
- `preview_privacy`:
  - `full`: Shows message body and author in notification banner.
  - `sender_only`: Shows author identity with generic "Sent you a message" text.
  - `hidden`: Suppresses author and content completely ("New notification").
