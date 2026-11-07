# PHASE 29.1 — MEDIA STORAGE VALIDATION SPECIFICATION

## 1. Storage Adapter Status
- **Active Adapter**: `local-dev-filesystem` (Local storage under `backend/storage/`).
- **S3/R2 Cloud Adapter**: Code implementation verified in `backend/app/services/media_service.py` (`S3StorageAdapter`).
- **CDN Status**: Direct streaming active; edge CDN requires `MEDIA_CDN_BASE_URL`.

---

## 2. Ingestion & Security Validation Checks

### 2.1 File Validation Integrity
- **MIME Whitelist**: Strictly enforces allowed extensions (`image/jpeg` -> `.jpg`, `video/mp4` -> `.mp4`, `audio/mp4` -> `.m4a`).
- **Magic-Byte Sniffing**: Binary headers verified against genuine signatures:
  - Valid MP4 (`\x00\x00\x00\x18ftyp`): `True`
  - Spoofed EXE disguised as video: `False` (Rejected with `400 Bad Request`)
- **Size Quotas**: Enforced at gateway (15MB images, 100MB local video, 500MB cloud presigned).

---

## 3. Staging S3 / Cloudflare R2 Activation Guide

To switch from local development storage to Cloudflare R2 / AWS S3 in staging:

```bash
MEDIA_S3_ACCESS_KEY_ID="your_access_key"
MEDIA_S3_SECRET_ACCESS_KEY="your_secret_key"
MEDIA_S3_BUCKET="zynova-staging-media"
MEDIA_S3_REGION="auto"
MEDIA_S3_ENDPOINT_URL="https://<account_id>.r2.cloudflarestorage.com"
MEDIA_CDN_BASE_URL="https://cdn-staging.intellidev.in"
```
When configured, `get_storage_adapter()` automatically transitions to `S3StorageAdapter` without requiring code changes.
