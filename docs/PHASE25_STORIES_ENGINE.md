# ZYNOVA 3.0 — PHASE 25: STORIES ENGINE SPECIFICATION
**Document ID:** DOC-PHASE25-STORIES-001  

---

## 1. 24-HOUR LIFECYCLE & PRUNING

- **Creation**: `expires_at` is computed using UTC timezone (`datetime.now(timezone.utc) + timedelta(hours=24)`).
- **MongoDB TTL Index**: Index on `expires_at` (`expireAfterSeconds=0`) removes documents automatically.
- **Application Query Guard**: The backend never assumes TTL has pruned expired stories; every database query enforces `expires_at: {"$gt": now}`.

---

## 2. PRIVACY & ACCESS CONTROL

1. **Public vs Private Creators**: Follow status verified before returning story payloads.
2. **Close Friends List**: Stored in `users.social_profile.close_friends`. If `is_close_friends_only` is true, the viewer ID must exist in the author's close friends list.
3. **Mutual Blocking**: Stories are never returned if either party has blocked the other.
4. **Author-Only Viewers**: `GET /social/stories/{id}/viewers` checks `story.author_id == current_user.id`, returning HTTP 403 Forbidden for non-authors.
