# PHASE 27 — COMPLETE API REFERENCE SPECIFICATION

Base Path: `/api/v1/videos`

---

## 1. Channel Management

### `POST /channels`
Create or update the authenticated user's video channel.
- **Auth**: Bearer JWT
- **Request Body**:
  ```json
  {
    "handle": "tech_hub",
    "name": "Tech Hub Official",
    "description": "Tech reviews and tutorials",
    "avatar_url": "https://cdn.zynova.net/avatars/tech.jpg",
    "banner_url": "https://cdn.zynova.net/banners/tech.jpg"
  }
  ```
- **Response**: `200 OK` ChannelResponse

### `GET /channels/{channel_id}`
Retrieve public channel details by Channel ID or Unique Handle.
- **Auth**: None (Optional)
- **Response**: `200 OK` ChannelResponse

### `POST /channels/{channel_id}/subscribe`
Toggle subscription status to a channel (cannot subscribe to self).
- **Auth**: Bearer JWT
- **Response**: `200 OK`
  ```json
  {
    "subscribed": true,
    "subscribers_count": 1420
  }
  ```

### `GET /channels/{channel_id}/analytics`
Retrieve channel performance metrics (Owner only).
- **Auth**: Bearer JWT
- **Response**: `200 OK` CreatorAnalyticsResponse

---

## 2. Video Upload & Discovery

### `POST /`
Upload a new video or short.
- **Auth**: Bearer JWT
- **Form Data**:
  - `file`: Binary file (mp4, webm, mov, <=100MB)
  - `title`: String (1-150 chars)
  - `description`: String (optional)
  - `category`: String (e.g., "Technology", "Gaming")
  - `is_short`: Boolean (true for 9:16 vertical shorts <=60s)
  - `visibility`: "public" | "unlisted" | "private"
- **Response**: `201 Created` VideoResponse

### `GET /`
List feed videos with optional category filtering and cursor pagination.
- **Auth**: None
- **Query Params**: `category` (string), `limit` (int, default 20), `cursor` (string)
- **Response**: `200 OK` `List[VideoResponse]`

### `GET /shorts`
Retrieve paginated vertical shorts feed.
- **Auth**: None
- **Query Params**: `limit` (int, default 15), `cursor` (string)
- **Response**: `200 OK` `List[VideoResponse]`

### `GET /recommendations`
Explainable video recommendations tailored by view history and channel subscriptions.
- **Auth**: None (Optional JWT)
- **Query Params**: `limit` (int, default 20)
- **Response**: `200 OK` `List[VideoResponse]`

---

## 3. Playback & Engagement

### `GET /{id}`
Retrieve video metadata.
- **Auth**: Optional (Required if visibility is "private")
- **Response**: `200 OK` VideoResponse (or `403 Forbidden` if private and caller != owner)

### `GET /{id}/stream`
Stream video binary with HTTP 206 Partial Content byte ranges.
- **Auth**: Optional (Required if visibility is "private")
- **Headers**: `Range: bytes=0-1048575`
- **Response**: `206 Partial Content` (or `403 Forbidden`)

### `POST /{id}/view`
Register a view count with 60-second cooldown deduplication.
- **Auth**: Optional
- **Response**: `200 OK` `{"success": true, "counted": true, "views_count": 89}`

### `POST /{id}/feedback`
Toggle like or dislike status.
- **Auth**: Bearer JWT
- **Request Body**: `{"action": "like"}` (or `"dislike"`)
- **Response**: `200 OK`
  ```json
  {
    "status": "added",
    "likes_count": 12,
    "dislikes_count": 0,
    "user_feedback": "like"
  }
  ```

### `POST /{id}/progress`
Save watch playback heartbeat and update resume position.
- **Auth**: Bearer JWT
- **Request Body**:
  ```json
  {
    "current_time_seconds": 124.5,
    "duration_seconds": 360.0,
    "completed": false
  }
  ```
- **Response**: `200 OK` `{"saved": true}`

### `GET /user/history`
Retrieve watch history for the authenticated user.
- **Auth**: Bearer JWT
- **Response**: `200 OK` `List[WatchHistoryResponse]`

---

## 4. Playlists

### `POST /playlists`
Create a user playlist.
- **Auth**: Bearer JWT
- **Request Body**: `{"title": "My Favorites", "description": "Best clips", "is_private": false}`
- **Response**: `201 Created` PlaylistResponse

### `POST /playlists/{playlist_id}/videos`
Add or remove a video from a playlist.
- **Auth**: Bearer JWT
- **Request Body**: `{"video_id": "67cd...", "action": "add"}`
- **Response**: `200 OK` PlaylistResponse
