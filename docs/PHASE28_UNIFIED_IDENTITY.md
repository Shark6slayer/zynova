# PHASE 28 — UNIFIED IDENTITY & LIFECYCLE ARCHITECTURE

## 1. Single Account Principle
In Zynova, each user possesses exactly one account record in the primary `users` collection. There are no secondary shadow accounts or duplicated user records for Social, Connect, or Video.

---

## 2. Identity Data Schema

```json
{
  "_id": "ObjectId('67cda...b1')",
  "email": "user@zynova.net",
  "username": "karuppusamy",
  "full_name": "Karuppusamy C",
  "avatar_url": "https://cdn.zynova.net/avatars/user.jpg",
  "bio": "Building the future of unified social platforms.",
  "is_active": true,
  "social_profile": {
    "is_private": false,
    "website": "https://intellidev.in",
    "pronouns": "they/them",
    "allow_story_replies": "everyone",
    "allow_mentions": "everyone",
    "show_activity_status": true
  },
  "connect_profile": {
    "display_name": "Karuppusamy (Zynova)",
    "about_text": "Available for discussions.",
    "last_seen_privacy": "everyone",
    "read_receipts_enabled": true
  },
  "video_channel": {
    "handle": "karuppusamy_tech",
    "channel_name": "Tech Channel",
    "channel_description": "Tech reviews & guides",
    "banner_url": "https://cdn.zynova.net/banners/tech.jpg",
    "subscribers_count": 1420
  },
  "blocked_users": ["67cdb...c2"]
}
```

---

## 3. Account Lifecycle Policies

### 3.1 Temporary Deactivation (`POST /api/v1/users/me/deactivate`)
- Validates current password.
- Sets `is_active = false`.
- Records `deactivated_at` timestamp.
- Immediately invalidates all active sessions and refresh tokens.
- Hides user from search indices and public discovery feeds while preserving underlying data for instant restoration upon re-login.

### 3.2 Irreversible Cascade Deletion (`DELETE /api/v1/users/me`)
In strict adherence to the Digital Personal Data Protection (DPDP) Act, account deletion executes an atomic cascade:
1. **Sessions & Credentials**: Revokes all active JWT tokens and device sessions (`device_sessions`, `refresh_tokens`).
2. **Preferences & Search**: Deletes `user_preferences`, `notification_preferences`, and `search_history`.
3. **Social Subsystem**: Deletes authored posts (`posts`), comments (`post_comments`), bookmarks, and follow relationships (`social_follows`).
4. **Connect Subsystem**: Deletes chat messages (`connect_messages`), ephemeral status, and cryptographic pre-keys.
5. **Video Subsystem**: Deletes creator channels (`creator_channels`), video uploads (`videos`), and watch history (`watch_progress`).
6. **Primary Record**: Removes primary document from `users`.
