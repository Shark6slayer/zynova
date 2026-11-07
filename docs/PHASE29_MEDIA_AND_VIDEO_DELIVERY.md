# PHASE 29 — MEDIA AND VIDEO DELIVERY PIPELINE

## 1. Storage Abstraction Architecture
Media operations utilize `MediaStorageService` (`backend/app/services/media_service.py`) supporting both local storage adapters and Cloudflare R2 / AWS S3 S3-compatible cloud storage.

---

## 2. Ingestion & Security Validation Pipeline

1. **Client Request**: Initiates direct multipart upload (`/platform/media/upload`) or requests presigned URL (`/platform/media/presign`).
2. **Size Enforcement**: Strict limits checked before allocating disk/memory buffers:
   - Images (Avatars, Covers): Max 15 MB.
   - Audio: Max 25 MB.
   - Videos (Local storage): Max 100 MB.
   - Videos (Presigned R2/S3): Max 500 MB.
3. **MIME Magic-Byte Sniffing**: Header bytes are verified against genuine media signatures:
   - MP4: `\x00\x00\x00\x18ftyp` / `\x00\x00\x00\x20ftyp`
   - WebM / MKV: `\x1a\x45\xdf\xa3`
   - JPEG: `\xff\xd8\xff`
   - PNG: `\x89PNG\r\n\x1a\n`
4. **Quarantine & Malware Scan**: Uploaded binaries pass through `scan_quarantined_media` before being promoted to active storage.

---

## 3. Video Streaming & Adaptive Bitrate Disclosure
- **Current Operational Delivery**: HTTP 206 Partial Content byte-range streaming (`/videos/{id}/stream`), allowing progressive downloading and seeking.
- **Adaptive Bitrate (HLS/DASH) Readiness Plan**: Multi-bitrate transcoding ladder (1080p, 720p, 480p, 360p) requires asynchronous worker nodes with FFmpeg hardware acceleration. For production scale, an asynchronous worker queue (Celery/RQ) listening on upload notifications is documented and scheduled for future deployment.
