# ZYNOVA 3.0 — PHASE 24.1: IDENTITY IMPLEMENTATION
**Document ID:** DOC-PHASE24-1-IDENTITY-001  
**Branch:** `feature/phase-24-1-backend-implementation`  
**Status:** Implemented & Verified  

## 1. APPROACH

The unified identity strategy uses the **single existing `users` collection** with lazily-initialised embedded sub-profiles. No duplicate account records are created for any platform.

## 2. SCHEMA ADDITIONS (LAZY DEFAULTS)

Each field is added to the user document on first access via `get_or_init_unified_profile()`:

| Field | Type | Purpose |
| :--- | :--- | :--- |
| `social_profile` | Object | Is-private toggle, website, pronouns, story reply/mention permissions |
| `connect_profile` | Object | Display name override, about text, last-seen privacy, receipt and indicator toggles |
| `video_channel` | Object | Channel handle (unique), channel name, description, banner URL, subscriber count |
| `privacy_settings` | Object | Profile visibility, search discoverability, data personalisation |
| `blocked_users` | List[str] | User IDs blocked by this user |
| `device_sessions` | List[Object] | Active device registrations (device_id, platform, push_token) |
| `account_status` | str | `active`, `suspended`, or `restricted` |

## 3. SERVICE: `backend/app/services/identity_service.py`

| Function | Description |
| :--- | :--- |
| `get_or_init_unified_profile(db, user_id)` | Returns full profile, lazily writing defaults for missing sub-profiles |
| `update_social_profile(db, user_id, updates)` | Writes whitelisted social settings via `$set` with `social_profile.` prefix |
| `update_connect_profile(db, user_id, updates)` | Same pattern for connect settings |
| `setup_video_channel(db, user_id, handle, name, desc)` | Claims unique `@handle`; enforces uniqueness via sparse index |
| `block_user(db, actor_id, target_id)` | Adds to `blocked_users`, removes bidirectional follows |
| `unblock_user(db, actor_id, target_id)` | Removes from `blocked_users` |
| `get_blocked_users(db, user_id)` | Returns list of blocked user IDs |
| `is_blocked(db, viewer_id, subject_id)` | Returns True if either party has blocked the other |
| `register_device_session(db, user_id, session)` | Upserts device session (removes old entry for same device_id) |
| `revoke_device_session(db, user_id, device_id)` | Removes device session and logs audit event |
| `get_device_sessions(db, user_id)` | Returns list of session objects (push tokens masked at route layer) |

## 4. BACKWARD COMPATIBILITY

- Existing `users` schema fields (`email`, `username`, `hashed_password`, `is_active`, `role`) are **unchanged**.
- Authentication (Argon2id + JWT + JTI revocation) is **unmodified**.
- All existing tests pass: **98/98 regression + 44/44 Phase 24.1 = 142 total**.

## 5. DATABASE INDEXES

- `users.video_channel.handle`: Unique sparse index — enforces `@handle` uniqueness globally.
- `users.account_status`: Single-field index — enables fast moderation queries.
