# ZYNOVA VIDEO — PLAYBACK & DELIVERY ENGINE
**HTTP 206 Partial Content Byte-Range Delivery and CDN Caching**  

---

## 1. Byte-Range Streaming Protocol (RFC 7233)

Playback is powered by FastAPI async file streaming supporting partial content requests:
- Request Header: `Range: bytes=start-end`
- Response Status: `206 Partial Content`
- Response Header: `Content-Range: bytes start-end/total_bytes`
- Chunk Size: Configured at 1MB to balance memory overhead and client buffer speed.

---

## 2. Playback Security & Range Authorization

- **Private Stream Guard**: Before returning stream chunks, `stream_video` checks the video's visibility. If `visibility == "private"`, unauthenticated or non-owner requests receive $403\text{ Forbidden}$.
- **Storage Path Isolation**: Physical storage paths (`storage_key`) are sanitized UUID filenames stored separately from user-provided titles, completely preventing directory traversal attacks.
