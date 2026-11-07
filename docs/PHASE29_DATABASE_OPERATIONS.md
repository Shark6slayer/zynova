# PHASE 29 — DATABASE OPERATIONS & ATLAS READINESS

## 1. Connection Pooling & Resiliency
The MongoDB client (`backend/app/database/client.py`) is configured with production connection controls:
- **Pool Size**: Managed via Motor connection pool defaults (up to 100 concurrent sockets per worker).
- **Timeouts**: `serverSelectionTimeoutMS=5000`, `connectTimeoutMS=10000`, `socketTimeoutMS=10000`.
- **TLS Security**: Enforces verified CA certificates from `certifi.where()` for all Atlas cluster connections (`mongodb+srv://`).

---

## 2. Production Index Topology

| Collection | Indexed Keys | Constraints / Type | Purpose |
| :--- | :--- | :--- | :--- |
| `users` | `email` | `unique=True` | Unique login identity |
| `users` | `username` | `unique=True` | Unique handle |
| `users` | `is_active` | Standard | Active profile discovery filtering |
| `posts` | `author_id`, `created_at` | Compound `(-1)` | Author timeline query |
| `posts` | `media_type`, `created_at` | Compound `(-1)` | Reels feed discovery |
| `posts` | `tags` | Multikey | Hashtag search |
| `videos` | `owner_id`, `created_at` | Compound `(-1)` | Creator studio video lists |
| `videos` | `is_short`, `visibility`, `created_at` | Compound `(-1)` | Shorts swipe feed |
| `creator_channels` | `handle` | `unique=True` | Unique creator channel URL |
| `connect_messages` | `conversation_id`, `created_at`| Compound `(-1)` | Chat history retrieval |
| `revoked_tokens` | `expires_at` | `expireAfterSeconds=0` | Automatic TTL cleanup of revoked JWTs |
| `notifications` | `user_id`, `read`, `created_at`| Compound `(-1)` | Unread badges and notification feed |

---

## 3. Account Deletion Atomicity & Cascade Strategy
In MongoDB Atlas standalone or replica sets without cross-document multi-collection transaction coordination, a multi-collection cascade is executed with retryable steps:
1. Active session and refresh token revocation.
2. User preferences, notification preferences, and search history deletion.
3. Social posts, post comments, follow records, and bookmarks deletion.
4. Connect messages, ephemeral statuses, and cryptographic pre-keys deletion.
5. Creator channels, video uploads, and watch progress deletion.
6. Primary user record deletion.
Each step logs progress to prevent orphaned resources if interrupted.
