# PHASE 28 — UNIFIED MEDIA INFRASTRUCTURE & INTEGRATION AUDIT

## 1. Storage Abstraction Overview
All media operations across Social, Connect, and Video utilize the unified `MediaStorageService` implemented in Phase 24.1 (`backend/app/services/media_service.py`).

```
                    [Client Upload Request]
                               │
               ┌───────────────┴───────────────┐
               ▼                               ▼
    [Local Storage Adapter]         [S3/R2 Cloud Adapter]
     - Development Mode              - Production Mode
     - Directory: backend/storage    - Presigned direct client upload
     - HTTP 206 byte streaming       - Cloudflare CDN distribution
```

---

## 2. Ingestion Policies & MIME Security

### 2.1 File Validation Rules
- **Image Uploads**: Must match JPEG, PNG, or WebP headers; capped at 15MB.
- **Video Uploads**: Must match MP4 (`ftyp`), WebM (`\x1a\x45\xdf\xa3`), or QuickTime MOV; capped at 100MB in local mode (500MB via presigned cloud flow).
- **Audio Attachments**: AAC, MP3, Opus; capped at 25MB.

### 2.2 Quarantine & Path Traversal Prevention
- All uploaded files are assigned cryptographic UUID filenames (`uuid.uuid4().hex`) with sanitized file extensions.
- User-provided original filenames are stored purely as metadata and never used in filesystem paths.
- Content is stored outside the public document root and streamed strictly through authorized route controllers.
