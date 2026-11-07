# ZYNOVA 3.0 — PHASE 24.1: MEDIA SERVICE IMPLEMENTATION
**Document ID:** DOC-PHASE24-1-MEDIA-001  
**Branch:** `feature/phase-24-1-backend-implementation`  
**Status:** Implemented & Verified  

## 1. DESIGN PRINCIPLES

- **Credentials never reach the client.** Presigned URLs are generated server-side only.
- **Local dev adapter is explicitly labelled.** `LocalDevStorageAdapter` logs a prominent `⚠️ WARNING` and sets `adapter_name = "local-dev-filesystem"`.
- **All uploads are quarantined first.** Both multipart and presigned flows record assets as `pending_upload` or quarantine-then-promote before marking `active`.
- **Magic-byte validation** rejects file-type spoofing regardless of MIME headers.

## 2. STORAGE ADAPTERS

**File:** [`backend/app/services/media_service.py`](file:///c:/super_ai/backend/app/services/media_service.py)

| Adapter | Activation | Use Case |
| :--- | :--- | :--- |
| `LocalDevStorageAdapter` | No `MEDIA_S3_*` env vars set | Development / local testing only |
| `S3StorageAdapter` | `MEDIA_S3_ACCESS_KEY_ID` + `MEDIA_S3_BUCKET` set | Staging / Production (R2 or S3) |

**Factory:** `get_storage_adapter()` automatically selects the adapter based on config.

## 3. MIME WHITELIST AND FILE LIMITS

| Category | MIME Types | Max Size |
| :--- | :--- | :--- |
| Image | JPEG, PNG, WebP, GIF, AVIF | 15 MB |
| Video | MP4, QuickTime, WebM | 100 MB – 2 GB |
| Audio | AAC, MPEG, OGG, WebM audio | 20 MB |
| Document | PDF, ZIP | 50 MB |

## 4. UPLOAD FLOWS

### Backend Multipart (Dev / Small Files)
```
Client → POST /api/v1/platform/media/upload → FastAPI ingests, quarantines, scans, promotes
```

### Presigned Direct Upload (Production)
```
Client → POST /api/v1/platform/media/presign → Returns {asset_id, upload_url, upload_fields}
Client → PUT/POST directly to S3/R2 (no backend load)
Client → POST /api/v1/platform/media/confirm?asset_id={id} → Backend marks asset active
```

## 5. MALWARE SCAN INTEGRATION

Integrates the existing `backend/app/core/scanner.py`:
- **Development**: Mock EICAR scanner detects test signatures deterministically.
- **Staging/Production**: ClamAV TCP daemon at `CLAMAV_HOST:CLAMAV_PORT`.
- **Fail-closed**: In production with `CLAMAV_REQUIRED_IN_PRODUCTION=True`, ClamAV unavailability returns `HTTP 503`.

## 6. REQUIRED ENVIRONMENT VARIABLES (PRODUCTION)

```
MEDIA_S3_ACCESS_KEY_ID=<R2 or S3 key>
MEDIA_S3_SECRET_ACCESS_KEY=<secret>
MEDIA_S3_BUCKET=zynova-public-media
MEDIA_S3_ENDPOINT_URL=https://<account>.r2.cloudflarestorage.com
MEDIA_CDN_BASE_URL=https://cdn.intellidev.in/public
```

> [!CAUTION] Never commit these values to source control. Store in deployment environment secrets only.
