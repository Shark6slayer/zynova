# PHASE 27 — SECURITY AUDIT & ACCESS CONTROL SPECIFICATION

## 1. Executive Summary
This document outlines the security controls, authentication boundaries, and threat mitigation mechanisms implemented across the Zynova Video and Shorts subsystem in Phase 27. All implementations adhere to OWASP API Security Top 10 recommendations and strictly isolate private creator content.

---

## 2. Threat Models & Implemented Mitigations

### 2.1 Broken Object Level Authorization (BOLA / IDOR)
- **Vulnerability**: An attacker attempts to stream, modify, or delete another creator's unlisted or private video by guessing or enumerating the MongoDB `video_id`.
- **Mitigation**:
  - `GET /videos/{video_id}`: Checks `video.visibility`. If `private`, the system validates `current_user["_id"] == video["owner_id"]`. If unauthenticated or mismatched, raises HTTP 403 Forbidden.
  - `GET /videos/{video_id}/stream`: Range streaming strictly enforces private authorization *prior* to inspecting or opening file descriptors on disk, preventing file-presence probing via timing attacks.
  - `PATCH /videos/{video_id}` & `DELETE /videos/{video_id}`: Explicitly matches `owner_id`. Any cross-tenant modification raises HTTP 403.

### 2.2 Unrestricted File Upload & Remote Code Execution (RCE)
- **Vulnerability**: Attacker uploads malicious binaries, PHP/Python scripts, or HTML polyglots disguised as video files.
- **Mitigation**:
  - **MIME Magic-Byte Verification**: Uploaded streams are inspected via file header analysis. Files must match genuine video containers:
    - MP4: `\x00\x00\x00\x18ftyp` / `\x00\x00\x00\x20ftyp`
    - WebM/MKV: `\x1a\x45\xdf\xa3`
    - QuickTime MOV: `\x00\x00\x00\x14ftypqt`
  - **Extension Whitelist**: Only `.mp4`, `.webm`, `.mov` are permitted.
  - **Payload Size Limits**: Strict 100MB payload guard enforced at the gateway and route layer. Exceeding requests are terminated with HTTP 413 Payload Too Large.
  - **Path Traversal Shield**: Uploaded files are renamed using cryptographically secure UUIDv4 filenames and stored outside the public document root.

### 2.3 View Inflation & Denial-of-Service (DoS)
- **Vulnerability**: Botnets repeatedly calling view increments or like toggles to distort rankings or exhaust storage.
- **Mitigation**:
  - **View Cooldown Mechanism**: Views are deduplicated per `(user_id, video_id)` or `(client_ip, video_id)` within a sliding 60-second window. Rapid repeated pings return `{"counted": false}` without updating counters.
  - **Atomic Counter Operations**: Counter updates use MongoDB `$inc` operators preventing race conditions under concurrent requests.

### 2.4 Injection Attacks
- **Vulnerability**: Malicious payloads in comments, channel handles, or video descriptions.
- **Mitigation**:
  - Channel handles are restricted to alphanumeric and underscore characters `^[a-zA-Z0-9_]{3,30}$`.
  - Stored strings are sanitized and parameterized through Pydantic V2 schemas and Motor ODM.

---

## 3. Compliance & Audit Verification Matrix

| Endpoint | Auth Required | Scope / Rule | Verified Status |
| :--- | :--- | :--- | :--- |
| `POST /videos` | Yes (Bearer JWT) | Validates MIME, size, channel assignment | PASS |
| `GET /videos/{id}` | Conditional | Public/Unlisted open; Private requires Owner ID | PASS |
| `GET /videos/{id}/stream` | Conditional | Private video streams require Owner ID authorization (403 on mismatch) | PASS |
| `PATCH /videos/{id}` | Yes | Owner ID match only; 403 on mismatch | PASS |
| `DELETE /videos/{id}` | Yes | Owner ID match only; 403 on mismatch | PASS |
| `POST /videos/channels` | Yes | Unique handle validation, owner binding | PASS |
| `POST /videos/{id}/feedback` | Yes | Atomic like/dislike toggle | PASS |
