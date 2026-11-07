# ZYNOVA 3.0 — PHASE 25: DATABASE SCHEMA SPECIFICATION
**Document ID:** DOC-PHASE25-SCHEMA-001  
**Database:** MongoDB Atlas (`zynova_db`)  

---

## 1. COLLECTIONS DEFINITION

### `users` (Extended embedded `social_profile`)
```json
{
  "_id": ObjectId("..."),
  "username": "creator",
  "full_name": "Verified Creator",
  "avatar_url": "https://cdn.intellidev.in/public/avatars/...",
  "bio": "Building the sovereign cloud",
  "social_profile": {
    "is_private": false,
    "is_verified": true,
    "verified_at": ISODate("2026-11-07T..."),
    "website": "https://intellidev.in",
    "close_friends": ["uid1", "uid2"]
  },
  "blocked_users": []
}
```

### `social_stories` (With TTL Index)
```json
{
  "_id": ObjectId("..."),
  "author_id": "user_id",
  "media_url": "https://cdn.intellidev.in/public/stories/...",
  "media_type": "image",
  "caption": "Sunset in Bengaluru",
  "is_close_friends_only": false,
  "viewers": ["viewer_id_1"],
  "views_count": 1,
  "reactions": [{"user_id": "...", "reaction": "🔥"}],
  "created_at": ISODate("2026-11-07T10:00:00Z"),
  "expires_at": ISODate("2026-11-08T10:00:00Z")
}
```
*Index:* `expires_at` with `expireAfterSeconds=0`.

### `story_highlights`
```json
{
  "_id": ObjectId("..."),
  "author_id": "user_id",
  "title": "Roadtrips",
  "cover_image_url": "https://cdn...",
  "story_ids": ["story_1", "story_2"],
  "stories_count": 2,
  "created_at": ISODate("...")
}
```

### `social_notes`
```json
{
  "user_id": "user_id",
  "text": "Coding the social core 🎧",
  "music_title": "Blinding Lights",
  "music_artist": "The Weeknd",
  "created_at": ISODate("..."),
  "expires_at": ISODate("...")
}
```

### `verification_applications`
```json
{
  "_id": ObjectId("..."),
  "user_id": "user_id",
  "full_legal_name": "Aarav Sharma",
  "document_type": "passport",
  "evidence_urls": ["https://cdn.intellidev.in/secure/..."],
  "category": "creator",
  "reason": "Public figure verification",
  "status": "pending",
  "reviewer_notes": null,
  "created_at": ISODate("..."),
  "reviewed_at": null
}
```
