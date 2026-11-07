# ZYNOVA 3.0 — PHASE 24.1: NOTIFICATION FOUNDATION IMPLEMENTATION
**Document ID:** DOC-PHASE24-1-NOTIF-001  
**Branch:** `feature/phase-24-1-backend-implementation`  
**Status:** Existing service extended; new event types registered  

## 1. EXISTING FOUNDATION (PRESERVED)

The existing `notification_service.py` and `notifications.py` router provide:
- Paginated notification listing with category and read-state filters.
- `create_event_notification()` with idempotency (`event_id` unique index).
- Self-action suppression (actor_id == recipient_id → skip).
- Mark single / mark-all-read / delete / clear-read endpoints.
- Unread count endpoint for badge displays.

## 2. PHASE 24.1 NOTIFICATION EVENT TYPES

| Platform | Event Type | Trigger |
| :--- | :--- | :--- |
| **Social** | `social_follow` | User A follows User B |
| **Social** | `social_like` | User A likes User B's post |
| **Social** | `social_comment` | User A comments on User B's post |
| **Social** | `social_story_view` | (Phase 25) User A views User B's story |
| **Connect** | `connect_message` | (Phase 26) New direct message received |
| **Connect** | `connect_call_missed` | (Phase 26) Missed WebRTC call |
| **Video** | `video_new_upload` | (Phase 27) Subscribed channel publishes |
| **Video** | `video_comment` | (Phase 27) Comment on creator's video |
| **System** | `system_account_alert` | Account status change |

## 3. PUSH NOTIFICATION READINESS

Device push tokens are stored in `users.device_sessions[].push_token`. The notification service is designed to call a push dispatcher (FCM/APNs) when:
- Recipient has no active WebSocket connection.
- Event category matches user notification preferences.

**Phase 26** will activate the FCM/APNs dispatch layer for Zynova Connect messaging.

## 4. REAL-TIME DELIVERY VIA WEBSOCKET

When a notification is created via `create_event_notification()`, the caller may optionally trigger `enhanced_ws_manager.dispatch_event()` to deliver the notification badge count update in real-time. This pattern is already used in `social.py` for follow/like/comment events and is ready for all Phase 25–27 event types.
