# PHASE 24 — UNIFIED IDENTITY & PERMISSION ARCHITECTURE

**Document Reference:** `ZYNOVA-DOC-PHASE24-IDENTITY`  
**Execution Timestamp:** 2026-11-07T10:40:30+05:30  
**Evaluator:** Principal Security & Identity Architect  

---

## 1. UNIFIED USER IDENTITY TOPOLOGY

Zynova enforces **One User Account, One Identity** across all product verticals. A single user registered in the `users` collection accesses **Zynova Social**, **Zynova Connect**, and **Zynova Video** with shared credentials, a single UUID, and a consolidated profile document.

```
                         ┌────────────────────────────────────────┐
                         │           UNIFIED USER IDENTITY        │
                         │             `users` Collection         │
                         │    _id: ObjectId ("672a0f8b1c4...")    │
                         │    username: "aarav_sundaram"          │
                         │    email: "aarav@intellidev.in"        │
                         │    password_hash: Argon2id(...)        │
                         │    is_verified: true (Blue Badge)      │
                         └──────────────────┬─────────────────────┘
                                            │
               ┌────────────────────────────┼────────────────────────────┐
               │                            │                            │
               ▼                            ▼                            ▼
  ┌─────────────────────────┐  ┌─────────────────────────┐  ┌─────────────────────────┐
  │      ZYNOVA SOCIAL      │  │      ZYNOVA CONNECT     │  │       ZYNOVA VIDEO      │
  │                         │  │                         │  │                         │
  │ • Social Handle & Bio   │  │ • Phone Verification    │  │ • Creator Channel Name  │
  │ • Followers & Following │  │ • End-to-End Key Bundle │  │ • Subscriber Base       │
  │ • Posts, Reels, Stories │  │ • Contacts & Chat Sync  │  │ • Channel Playlists     │
  │ • Account Privacy (Lock)│  │ • Call Capabilities    │  │ • Creator Analytics    │
  └─────────────────────────┘  └─────────────────────────┘  └─────────────────────────┘
```

---

## 2. UNIFIED USER SCHEMA SPECIFICATION

The primary `users` document encapsulates shared auth with embedded sub-documents for vertical-specific metadata:

```json
{
  "_id": "ObjectId('672a0f8b1c4e92a0')",
  "email": "aarav@intellidev.in",
  "username": "aarav_sundaram",
  "full_name": "Aarav Sundaram",
  "password_hash": "$argon2id$v=19$m=65536,t=3,p=4$...",
  "avatar_url": "https://cdn.intellidev.in/avatars/672a0f8b.webp",
  "is_active": true,
  "is_verified": true,
  "roles": ["user", "creator", "verified_partner"],
  "created_at": "2026-10-14T12:00:00Z",
  "updated_at": "2026-11-07T10:00:00Z",
  
  "social_profile": {
    "bio": "Building sovereign platforms for India 🇮🇳 | Photography & Tech",
    "is_private": false,
    "followers_count": 1420,
    "following_count": 380,
    "posts_count": 86,
    "saved_posts": [],
    "blocked_user_ids": []
  },
  
  "connect_profile": {
    "phone_hash": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "status_text": "Hey there! I am using Zynova Connect",
    "public_identity_key": "MCowBQYDK2VwAyEA...",
    "prekey_bundle_id": "bundle_982a",
    "last_seen_privacy": "everyone",
    "read_receipts_enabled": true
  },
  
  "video_channel": {
    "channel_id": "chan_672a0f8b",
    "channel_name": "Aarav Tech & Systems",
    "handle": "@aaravsystems",
    "subscribers_count": 12850,
    "total_views": 482000,
    "banner_url": "https://cdn.intellidev.in/banners/chan_672a.webp"
  }
}
```

---

## 3. UNIFIED SESSION & DEVICE MANAGEMENT

- **JWT Tokens:** Carry unified user claims:
  ```json
  {
    "sub": "672a0f8b1c4e92a0",
    "username": "aarav_sundaram",
    "roles": ["user", "creator"],
    "jti": "jti_49a8f2c",
    "exp": 1794025000
  }
  ```
- **Device Sessions (`device_sessions` collection):** Tracks multi-device logins (Web browser, Android mobile, Desktop app).
- **Session Revocation:** Users can view all active logged-in devices and revoke sessions instantly from their settings screen.
- **Mutual Blocking Protocol:**
  - Blocking a user on Zynova Social immediately blocks them on Zynova Connect and Zynova Video.
  - Blocked users cannot view posts, send chat messages, or comment on creator videos.
