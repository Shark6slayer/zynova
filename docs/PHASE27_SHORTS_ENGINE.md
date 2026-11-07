# ZYNOVA VIDEO — SHORTS ENGINE
**Vertical 9:16 Video Feeds, Audio Metadata, and Swipe Mechanics**  

---

## 1. Vertical Format Validation

- **Aspect Ratio Policy**: Shorts are tagged with `aspect_ratio: "9:16"` and `is_short: true`.
- **Duration Policy**: Shorts are capped at 60 seconds duration to maintain high retention and rapid swipe consumption.
- **Audio Metadata**: Supports sound attribution with `audio_title` and `audio_artist`.

---

## 2. Swipe Feed Retrieval

The dedicated Shorts endpoint `GET /api/v1/videos/shorts` serves paginated batches:
- Indexed strictly by `{"is_short": 1, "visibility": 1, "created_at": -1}`.
- Prunes blocked creators in-flight using `{"owner_id": {"$nin": blocked}}`.
- Optimized for mobile viewports and instant video element pre-caching.
