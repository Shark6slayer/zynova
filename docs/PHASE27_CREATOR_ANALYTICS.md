# PHASE 27 — CREATOR ANALYTICS & AUDIENCE RETENTION ARCHITECTURE

## 1. Overview
The Zynova Video Creator Analytics engine aggregates performance metrics across long-form video and vertical shorts content without introducing external heavy analytics frameworks or paid monetization infrastructure. It powers creator studio dashboards with verifiable watch metrics, retention telemetry, and subscriber conversion data.

---

## 2. Core Metrics Architecture

### 2.1 Metric Definitions
- **Total Views**: Sum of verified views recorded across all published videos owned by the channel.
- **Estimated Watch Time (Seconds)**: Aggregated seconds from watch progress heartbeat pings (`record_watch_progress`) across all viewers.
- **Audience Retention Rate**: Computed as `(total_seconds_watched / total_video_duration_seconds) * 100`, bounded between 0% and 100%.
- **Subscriber Count & Velocity**: Net active subscribers following the channel.
- **Engagement Ratios**: Aggregated likes, dislikes, and comments per view count.

### 2.2 Data Pipeline
```
[Client Playback Event] 
         │ (POST /videos/{id}/progress every 5s/pause/leave)
         ▼
[Watch Progress Service] ───► MongoDB `watch_progress` Collection (User/Video Pair)
         │
         ├───► Update `videos.watch_time_seconds`
         └───► Compute Aggregates on demand (GET /videos/channels/{handle}/analytics)
```

---

## 3. Analytics Schema & Aggregation Pipeline

### 3.1 Aggregation Strategy
Analytics are calculated dynamically over MongoDB collections using compound indexed queries:

```python
pipeline = [
    {"$match": {"owner_id": owner_id}},
    {
        "$group": {
            "_id": "$owner_id",
            "total_views": {"$sum": "$views_count"},
            "total_likes": {"$sum": "$likes_count"},
            "total_dislikes": {"$sum": "$dislikes_count"},
            "total_comments": {"$sum": "$comments_count"},
            "total_videos": {"$sum": 1},
        }
    }
]
```

### 3.2 Watch Progress Model
```python
class WatchProgressPayload(BaseModel):
    current_time_seconds: float
    duration_seconds: float
    completed: bool = False
```

Recorded documents in `watch_progress`:
- `user_id`: Viewer ObjectId / string
- `video_id`: Target video ObjectId
- `current_time`: Timestamp of last observed frame
- `duration`: Stated video length
- `completion_ratio`: `current_time / duration`
- `updated_at`: ISO timestamp

---

## 4. Privacy & Authorization
1. **Creator-Only Access**: The `/videos/channels/{channel_id}/analytics` endpoint strictly enforces `current_user["_id"] == channel["owner_id"]`. Unauthorized users receive HTTP 403 Forbidden.
2. **Viewer Anonymity**: Viewer IDs in watch progress are pseudonymized in public facing counts; no PII is returned in creator studio dashboards.
3. **No Financial Reporting**: Consistent with Phase 27 boundaries, all revenue, RPM, CPM, and payout calculations are strictly absent.
