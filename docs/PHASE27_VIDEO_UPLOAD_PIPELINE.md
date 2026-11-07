# ZYNOVA VIDEO — UPLOAD & PUBLISHING PIPELINE
**Media Ingestion, Quarantine Scanning, and Multipart Storage**  

---

## 1. Ingestion Pipeline & Magic-Byte Verification

Uploaded video binaries traverse a mandatory security boundary:
1. **MIME Verification**: Content-Type header must belong to allowed set (`video/mp4`, `video/webm`, `video/ogg`, `video/quicktime`).
2. **Magic Signature Inspection**: The initial 32 bytes are inspected for `ftyp` (MP4/MOV), `\x1a\x45\xdf\xa3` (WebM), or `OggS` signatures. Non-matching files are immediately rejected.
3. **Quarantine Writing**: Files are written to `QUARANTINE_DIR` before final storage promotion.
4. **Antivirus / Malware Scan**: Scanned via `scan_quarantined_media` before moving to permanent video storage.

---

## 2. Visibility & Publishing States

- `public`: Discoverable in search, home feed, recommendations, and creator channel pages.
- `unlisted`: Accessible only via direct URL reference; excluded from public feeds and search indices.
- `private`: Strictly restricted to the creator (`owner_id`); unauthorized access yields $403\text{ Forbidden}$.
