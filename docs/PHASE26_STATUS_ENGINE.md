# ZYNOVA CONNECT — STATUS & UPDATES ENGINE
**Ephemeral Status Lifecycle, Expiration, and Viewer Receipts**  

---

## 1. 24-Hour Expiration Mechanics

Status updates automatically expire 24 hours after creation (`expires_at = created_at + 24h`):
1. **Engine Level**: Background MongoDB index `{"expires_at": 1}` with `expireAfterSeconds: 0` purges documents.
2. **API Level**: All read queries strictly enforce `{"expires_at": {"$gt": now}}`.

---

## 2. Privacy & Viewer Tracking

- **Privacy Controls**:
  - `contacts`: Visible only to mutual followers/contacts.
  - `close_friends`: Filtered against the author's close friends list.
  - `public`: Broad discovery.
- **View Receipts**:
  - Viewers record their read status via `POST /api/v1/chat/status/{id}/view`.
  - Stored via atomic `$addToSet` to prevent duplicate view inflation.
