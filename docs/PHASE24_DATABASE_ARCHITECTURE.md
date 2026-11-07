# PHASE 24 — DATABASE ARCHITECTURE & SCHEMA SPECIFICATION

**Document Reference:** `ZYNOVA-DOC-PHASE24-DB-ARCH`  
**Execution Timestamp:** 2026-11-07T10:41:00+05:30  
**Evaluator:** Principal Database Architect & Data Engineer  

---

## 1. COMPREHENSIVE COLLECTION CATALOGUE

MongoDB Atlas serves as the core document database across all three product verticals.

```
                          ZYNOVA UNIFIED DATABASE (`zynova_db`)
                                            │
        ┌───────────────────────────────────┼───────────────────────────────────┐
        │                                   │                                   │
        ▼                                   ▼                                   ▼
 ┌──────────────┐                    ┌──────────────┐                    ┌──────────────┐
 │ SOCIAL DATA  │                    │ CONNECT DATA │                    │  VIDEO DATA  │
 ├──────────────┤                    ├──────────────┤                    ├──────────────┤
 │ • posts      │                    │ • connect_   │                    │ • channels   │
 │ • stories    │                    │   conversations                   │ • videos     │
 │ • follows    │                    │ • connect_   │                    │ • playlists  │
 │ • post_likes │                    │   messages   │                    │ • video_     │
 │ • post_      │                    │ • connect_   │                    │   comments   │
 │   comments   │                    │   groups     │                    │ • watch_     │
 │ • hashtags   │                    │ • call_      │                    │   history    │
 └──────────────┘                    │   sessions   │                    │ • channel_   │
                                     └──────────────┘                    │   subs       │
                                                                         └──────────────┘
```

---

## 2. COLLECTION SCHEMAS & COMPOUND INDEXES

### A. Social Module Collections

#### 1. `posts`
```json
{
  "_id": "ObjectId",
  "user_id": "ObjectId",
  "media_type": "image | video | reel",
  "media_urls": ["string"],
  "caption": "string",
  "hashtags": ["string"],
  "mentions": ["ObjectId"],
  "likes_count": 0,
  "comments_count": 0,
  "shares_count": 0,
  "is_archived": false,
  "visibility": "public | followers | close_friends",
  "created_at": "ISODate"
}
```
- **Indexes:**
  - `{"user_id": 1, "created_at": -1}` (User timeline pagination)
  - `{"hashtags": 1, "created_at": -1}` (Hashtag discovery)
  - `{"visibility": 1, "created_at": -1}` (Global explore feed)

#### 2. `stories`
Ephemeral social stories automatically expiring after 24 hours.
- **Fields:** `user_id`, `media_url`, `media_type`, `viewers`: `[{"user_id": ObjectId, "viewed_at": ISODate}]`, `expires_at`: `ISODate`.
- **Indexes:**
  - `{"expires_at": 1}` with **TTL index (`expireAfterSeconds: 0`)** for automated background purging.
  - `{"user_id": 1, "expires_at": -1}`.

#### 3. `follows`
- **Fields:** `follower_id: ObjectId`, `following_id: ObjectId`, `status: 'accepted' | 'pending'`, `created_at: ISODate`.
- **Indexes:**
  - `{"follower_id": 1, "following_id": 1}` (**Unique compound constraint**)
  - `{"following_id": 1, "status": 1}` (Follower query lookup)

---

### B. Connect Module Collections

#### 1. `connect_conversations`
- **Fields:**
  - `id: str` (UUID)
  - `is_group: bool`
  - `group_metadata`: `{"name": str, "avatar": str, "admins": [ObjectId], "creator": ObjectId}`
  - `participants: [ObjectId]`
  - `last_message`: `{"text": str, "sender_id": ObjectId, "created_at": ISODate}`
  - `pinned_by: [ObjectId]`
  - `archived_by: [ObjectId]`
  - `updated_at: ISODate`
- **Indexes:**
  - `{"participants": 1, "updated_at": -1}` (Inbox list sorting)

#### 2. `connect_messages`
- **Fields:**
  - `id: str` (UUID)
  - `conversation_id: str`
  - `sender_id: ObjectId`
  - `message_type: 'text' | 'image' | 'video' | 'audio' | 'document' | 'voice_note'`
  - `content: str` (Encrypted payload or plain text)
  - `media_asset_id: Optional[ObjectId]`
  - `reply_to_message_id: Optional[str]`
  - `delivery_status`: `{"sent": true, "delivered_to": [ObjectId], "read_by": [ObjectId]}`
  - `reactions`: `[{"emoji": str, "user_id": ObjectId}]`
  - `is_deleted_for_everyone: bool`
  - `created_at: ISODate`
- **Indexes:**
  - `{"conversation_id": 1, "created_at": -1}` (Chat transcript pagination)

---

### C. Video Module Collections

#### 1. `channels`
- **Fields:** `user_id: ObjectId`, `channel_name: str`, `handle: str` (unique), `description: str`, `avatar_url: str`, `banner_url: str`, `subscribers_count: int`, `created_at: ISODate`.
- **Indexes:**
  - `{"handle": 1}` (Unique)
  - `{"user_id": 1}` (Unique)

#### 2. `videos`
- **Fields:**
  - `id: str` (UUID)
  - `channel_id: ObjectId`
  - `creator_user_id: ObjectId`
  - `title: str`
  - `description: str`
  - `duration_seconds: float`
  - `is_short: bool` (Reel/Shorts format indicator)
  - `processing_status: 'uploading' | 'transcoding' | 'ready' | 'failed'`
  - `master_playlist_url: str` (HLS `.m3u8`)
  - `renditions`: `[{"resolution": "1080p", "bandwidth": 4500000, "url": str}]`
  - `thumbnail_url: str`
  - `views_count: int`
  - `likes_count: int`
  - `comments_count: int`
  - `tags: [str]`
  - `category: str`
  - `visibility: 'public' | 'unlisted' | 'private'`
  - `published_at: ISODate`
- **Indexes:**
  - `{"visibility": 1, "published_at": -1}` (Public feed & recommendations)
  - `{"channel_id": 1, "published_at": -1}` (Channel video listing)
  - `{"is_short": 1, "published_at": -1}` (Shorts vertical feed)

---

## 3. NON-DESTRUCTIVE EVOLUTION STRATEGY

- Existing collections (`users`, `user_preferences`, `posts`, `messages`, `videos`) remain fully backwards-compatible.
- New fields are added with optional default values (`None` or empty lists).
- Zero drop commands (`db.collection.drop()`) or schema destructions are permitted.
