# PHASE 28 — UNIFIED PLATFORM ARCHITECTURE

## 1. Executive Vision & Architecture Summary
Zynova is an integrated consumer ecosystem unifying three core pillars:
1. **Zynova Social** (Instagram-inspired): Posts, reels, stories, follower graphs, and social interactions.
2. **Zynova Connect** (WhatsApp-inspired): 1:1 direct messaging, group chats, communities, ephemeral status, and voice/video calling signaling.
3. **Zynova Video** (YouTube-inspired): 16:9 landscape videos, 9:16 vertical shorts, creator channels, playlists, and analytics.

Instead of three isolated silos, Phase 28 unifies them under a single identity backbone, shared media infrastructure, global search engine, unified notification center, cross-platform sharing router, and single-session settings.

```
                     ┌──────────────────────────────────────────────┐
                     │           Zynova Unified App Shell           │
                     │  Desktop Sidebar + Mobile Bottom Navigation  │
                     └──────────────────────┬───────────────────────┘
                                            │
               ┌────────────────────────────┼────────────────────────────┐
               ▼                            ▼                            ▼
      ┌─────────────────┐          ┌─────────────────┐          ┌─────────────────┐
      │  Zynova Social  │          │  Zynova Connect │          │   Zynova Video  │
      │  (Posts/Reels)  │          │  (Chats/Groups) │          │ (Videos/Shorts) │
      └────────┬────────┘          └────────┬────────┘          └────────┬────────┘
               │                            │                            │
               └────────────────────────────┼────────────────────────────┘
                                            │
                     ┌──────────────────────┴───────────────────────┐
                     │     Unified Platform Services (FastAPI)      │
                     ├──────────────────────────────────────────────┤
                     │ • Identity & Cascade Deletion (DPDP)         │
                     │ • Multi-Category Global Search Engine        │
                     │ • Unified Notification Center & Preferences  │
                     │ • Cross-Platform Share & Deep-Link Gateway   │
                     │ • Shared Media & MIME Quarantine Store       │
                     │ • Mutual Blocking & Privacy Enforcement      │
                     └──────────────────────┬───────────────────────┘
                                            │
                     ┌──────────────────────┴───────────────────────┐
                     │        MongoDB Atlas Shared Database         │
                     │  (users, posts, connect_*, videos, channels) │
                     └──────────────────────────────────────────────┘
```

---

## 2. Platform Component Integration Contracts

### 2.1 Identity Binding
All platform sub-profiles are embedded within a single document in the `users` collection:
- `users.social_profile`: Privacy, bio, website, activity status.
- `users.connect_profile`: Display name override, about text, read receipts, last seen privacy.
- `users.video_channel`: Creator channel handle, banner, subscriber counts, total views.
- `users.blocked_users`: Bidirectional blacklist enforced across search, direct messaging, post discovery, and channel interactions.

### 2.2 Shared Media Ingestion
Media is uploaded through `/api/v1/platform/media/upload` or presigned S3 URLs, categorized by purpose:
- `avatar`: Profile picture across Social, Connect, and Video.
- `social_post` & `social_story`: Images and short clips.
- `connect_attachment`: Encrypted/private media for chat exchanges.
- `video_thumbnail`: Cover images for long-form video and shorts.

### 2.3 Global Event Model
Key events trigger standardized notifications via `create_event_notification`:
- **Social**: `social_like`, `social_comment`, `social_follow`, `social_mention`.
- **Connect**: `connect_message`, `connect_group_invite`, `connect_call_missed`.
- **Video**: `video_subscription`, `video_upload`, `video_comment`.
All notifications carry a `navigation_target` deep link and are deduplicated via unique `event_id` tokens.
