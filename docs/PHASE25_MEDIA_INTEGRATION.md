# ZYNOVA 3.0 — PHASE 25: MEDIA INTEGRATION ARCHITECTURE
**Document ID:** DOC-PHASE25-MEDIA-001  

---

## 1. MEDIA STORAGE FLOW

Zynova Social supports dual media ingestion paths:
1. **Direct S3/R2 Presigned Upload (Production)**:
   - Requested via `/api/v1/platform/media/presign`.
   - Direct PUT/POST to Cloudflare R2 / AWS S3.
   - Confirmed via `/api/v1/platform/media/confirm`.
2. **Backend Multipart Upload (Dev & Mobile Fallback)**:
   - Handled via `/api/v1/social/media` with ClamAV quarantine scanning.

---

## 2. CAROUSELS & REELS CONSTRAINTS

- **Carousels**: Multi-image posts support up to 10 verified `media_assets` IDs referenced in `post.media_assets`.
- **Reels**: Vertical 9:16 video clips with FastStart MP4 or WebM encoding, capped at 100MB per reel.
- **Aspect Ratios**: Frontend renders responsive containers for 1:1 square, 4:5 portrait, and 9:16 vertical reels.
