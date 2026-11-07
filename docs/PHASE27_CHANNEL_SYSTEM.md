# ZYNOVA VIDEO — CREATOR CHANNEL SYSTEM
**Channel Identity, Handles, Customization, and Subscriptions**  

---

## 1. Unified Creator Identity

In Zynova, creator channels map directly to the unified `users` collection without requiring duplicate logins or second credentials:
- **Unique Handle**: Enforced case-insensitive alphanumeric handle (`^[a-zA-Z0-9_]+$`) stored in `creator_channels.handle`.
- **Channel Branding**: Channel name, banner image URL, avatar, and description.
- **Content Metrics**: Dynamic aggregations of `video_count`, `shorts_count`, and `subscriber_count`.

---

## 2. Subscription Lifecycle & Notifications

- **Subscribing**: `POST /api/v1/videos/channels/{channel_id}/subscribe` toggles subscriptions idempotently.
- **Self-Subscription Prevention**: Creators are prevented from subscribing to their own channel ($400\text{ Bad Request}$).
- **Notification Integration**: On subscription, the creator receives a real-time event notification (`channel_subscription`) via `create_event_notification`.
- **Privacy & Blocking**: Subscribing to a blocked creator or by a blocked user is rejected with $403\text{ Forbidden}$.
