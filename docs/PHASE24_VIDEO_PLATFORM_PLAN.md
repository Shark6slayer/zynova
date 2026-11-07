# ZYNOVA 3.0 — PHASE 24: VIDEO PLATFORM ARCHITECTURE PLAN
**Document ID:** DOC-PHASE24-VIDEO-001  
**Author:** Principal Video Systems Architect & Media Infrastructure Engineer  
**Status:** Approved Technical Plan  
**Module:** Zynova Video (YouTube-Inspired Experience)  

---

## 1. PRODUCT SPECIFICATION & VISION

**Zynova Video** is an adaptive, long-form and short-form video streaming and creator ecosystem:
1. **Creator Channels**: Custom channel handles (`@creator`), channel banners, creator bios, subscriber counter milestones, and featured playlists.
2. **Video Playback & Adaptive Bitrate**: Multi-quality HLS playback (1080p, 720p, 480p, 360p) with seamless quality auto-switching based on network bandwidth, playback speed control (0.25x to 2.0x), and picture-in-picture.
3. **Subscriptions & Notification Bell**: Real-time push and inbox alerts when subscribed channels upload new videos.
4. **Community Interactions**: Likes, dislikes (stored for recommendation algorithms), nested comment discussions with creator hearting, and video chapters.
5. **Playlists & Watch History**: Custom user-curated playlists, "Watch Later" queue, and resume-at-timestamp watch progress synchronization.
6. **Live Streaming Infrastructure**: Low-latency HLS (LL-HLS) and RTMP ingestion support for creator live broadcasts with synchronous live chat.
7. **Creator Studio Analytics**: Video view metrics, watch time duration, audience retention drop-off graphs, and traffic source breakdowns.

---

## 2. API ROUTE TAXONOMY & CONTRACTS

Prefix: `/api/v1/video`

### 2.1 Channels & Subscriptions
- `GET /video/channels/{handle}`: Retrieve channel metadata, subscriber count, and public videos.
- `PATCH /video/channels/me`: Customize channel name, handle, avatar, banner, and links.
- `POST /video/channels/{channel_id}/subscribe`: Subscribe/unsubscribe toggle with notification preference (`all`, `personalized`, `none`).
- `GET /video/subscriptions/feed`: Latest uploads from subscribed channels.

### 2.2 Video Catalog & Streaming
- `GET /video/feed`: Home video feed with algorithmic recommendation scoring.
- `POST /video/upload/initiate`: Initiate resumable video upload session (returns S3 multipart upload IDs or direct presigned upload).
- `POST /video/upload/complete`: Confirm upload and trigger FFmpeg HLS transcode job.
- `GET /video/watch/{video_id}`: Retrieve video playback manifest (`master.m3u8`), metadata, creator details, and chapter markers.
- `POST /video/watch/{video_id}/progress`: Update watch resume timestamp (e.g. `watched_seconds: 342`).
- `POST /video/watch/{video_id}/like`: Like / dislike toggle.

### 2.3 Comments & Community
- `GET /video/watch/{video_id}/comments`: Paginated top comments or newest comments.
- `POST /video/watch/{video_id}/comments`: Post a comment or reply.
- `POST /video/comments/{comment_id}/heart`: Creator-exclusive comment heart badge.

### 2.4 Playlists & Library
- `GET /video/library/history`: User watch history with watched progress indicators.
- `GET /video/library/playlists`: User's playlists (public and private).
- `POST /video/playlists`: Create new playlist.
- `POST /video/playlists/{playlist_id}/items`: Add/remove video from playlist.

---

## 3. ADAPTIVE STREAMING & CDN PLAYBACK ENGINE

Clients integrate standard HLS player libraries (e.g., `video.js`, `hls.js` on Web; `ExoPlayer` on Android):

```
                       [ Client HLS Player ]
                                │
                    1. Fetch Master Playlist
                                │
                                ▼
         [ CDN Edge: /hls/{video_id}/master.m3u8 ]
                                │
             (Returns Bitrate Manifest Ladder)
             - 1080p @ 4500 kbps (output_0.m3u8)
             - 720p  @ 2400 kbps (output_1.m3u8)
             - 480p  @ 1200 kbps (output_2.m3u8)
             - 360p  @ 600 kbps  (output_3.m3u8)
                                │
           2. Client selects optimal stream (e.g. 720p)
                                │
                                ▼
         [ CDN Edge: /hls/{video_id}/output_1.m3u8 ]
                                │
          3. Sequential 4-second TS chunk requests
         [ CDN Edge: /hls/{video_id}/segment_001.ts ]
```

---

## 4. CREATOR ANALYTICS & WATCH TIME TRACKING

Watch time events are batched on the client every 15 seconds to prevent DDoS load on the backend:
- Client payload: `{"video_id": "...", "watch_duration_seconds": 15, "current_timestamp": 145}`.
- Backend ingestion: Pushes payload to Redis stream `stream:video:watch_events`.
- Batch consumer: Aggregates metrics every 60 seconds and executes MongoDB atomic `$inc` updates:
  ```python
  await db.video_catalog.update_one(
      {"_id": video_id},
      {"$inc": {"view_count": 1, "total_watch_seconds": 15}}
  )
  ```
- **Anti-Fraud Filter**: Views are only credited if playback duration exceeds 30 continuous seconds or 50% of video duration for short videos.
