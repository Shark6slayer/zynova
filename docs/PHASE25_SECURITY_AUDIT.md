# ZYNOVA 3.0 — PHASE 25: APPLICATION SECURITY AUDIT
**Document ID:** DOC-PHASE25-SEC-001  

---

## 1. ACCESS CONTROL MATRIX

| Operation | Access Rule | Failure Code |
| :--- | :--- | :--- |
| View Profile | Allowed if unblocked. | HTTP 404 (Masks existence) |
| Follow Request | Instant follow if public; creates pending request if private. | HTTP 400 if blocked |
| View Posts | If author is private, viewer must be accepted follower. | Empty list / 403 |
| View Story Viewers | Strictly author-only (`story.author_id == user.id`). | HTTP 403 Forbidden |
| Review Verification | Admin role only (`current_user.role == 'admin'`). | HTTP 403 Forbidden |
| Edit/Delete Post | Post creator only (`post.author_id == user.id`). | HTTP 403 Forbidden |
| Delete Comment | Comment author or parent post author. | HTTP 403 Forbidden |

---

## 2. TAMPER-PROOF AUDIT LOGGING

Critical social actions generate tamper-proof audit records via `log_security_event()`:
- `USER_BLOCKED`: Logs actor, target, and timestamp.
- `VERIFICATION_SUBMITTED`: Logs application category and evidence URLs.
- `VERIFICATION_REVIEWED`: Logs admin reviewer ID, final status, and audit notes.
