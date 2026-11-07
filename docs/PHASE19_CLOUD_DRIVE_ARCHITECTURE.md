# PHASE 19 — CLOUD DRIVE OBJECT STORAGE ARCHITECTURE

**Document Reference:** `ZYNOVA-DOC-PHASE19-STORAGE`  
**Execution Timestamp:** 2026-11-07T09:51:00+05:30  
**Evaluator:** Principal Cloud Storage Architect & Security Engineer  

---

## 1. CURRENT REPOSITORY IMPLEMENTATION STATUS

- **Frontend View (`CloudDriveView.tsx`):**
  - Manages a client-side vault persisted to browser `localStorage` / `IndexedDB` under the key `super_ai_local_files_{userId}`.
  - Correctly avoids fabricating remote quota usage or simulated multi-gigabyte cloud capacities.
- **Backend Infrastructure:**
  - Zero object storage drivers (Boto3, MinIO, or S3 client) are currently registered in `requirements.txt` or mounted under `backend/app/api/routes/`.
  - **Verdict:** Local-only client vault. No remote cloud object storage exists.

---

## 2. PRODUCTION CLOUDFLARE R2 / AWS S3 HYBRID ARCHITECTURE

```
┌──────────────┐        1. Request Upload URL (File Meta)     ┌────────────────────────┐
│              ├─────────────────────────────────────────────►│  Zynova FastAPI Backend│
│              │◄─────────────────────────────────────────────┤  (Validates Quota/MIME)│
│              │        2. Return Signed PUT URL (15m TTL)    └────────────┬───────────┘
│  Zynova Web  │                                                           │
│  / Mobile UI │        3. Direct Binary Upload (PUT)                      │ Persist Metadata
│              ├──────────────────────────────┐                            ▼
│              │                              │               ┌────────────────────────┐
│              │                              ▼               │ MongoDB `user_files`   │
│              │                 ┌────────────────────────┐   │ status: 'pending_scan' │
│              │                 │   Cloudflare R2 Bucket │   └────────────────────────┘
│              │◄────────────────┤   (Zero Egress Fees)   │
│              │  4. HTTP 200    └────────────┬───────────┘
└──────────────┘                              │
                                              ▼
                         ┌────────────────────────────────────────┐
                         │ Event Notification / Quarantine Worker  │
                         │ - Scan file headers for EICAR / ClamAV │
                         │ - Compute SHA-256 binary digest        │
                         │ - Transition status: 'available'       │
                         └────────────────────────────────────────┘
```

---

## 3. CORE TECHNICAL SPECIFICATIONS

1. **Zero Secret Exposure:**
   - S3/R2 Access Keys (`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`) remain strictly encapsulated on the FastAPI server.
   - The frontend receives only time-limited, single-object presigned URLs (`generate_presigned_url('put_object', ...)`).
2. **Quota & File Size Enforcement:**
   - Free Tier User Quota: **1.0 GB** total storage.
   - Maximum Single Upload: **25.0 MB** per file.
   - Enforcement occurs server-side prior to issuing presigned upload credentials.
3. **MIME Validation & Extension Whitelisting:**
   - Permitted types: `image/jpeg`, `image/png`, `image/webp`, `application/pdf`, `text/plain`, `application/vnd.openxmlformats-officedocument.*`.
   - Executable formats (`.exe`, `.sh`, `.bat`, `.apk`, `.js`) are rejected at the presigned URL generation stage.
4. **Soft Deletion & Recovery Window:**
   - Files deleted by users enter a 30-day `marked_for_deletion` soft-delete state before permanent bucket lifecycle purging.

