# ZYNOVA 3.0 — PHASE 25: FEED & STORIES ENGINE SPECIFICATION
**Document ID:** DOC-PHASE25-ENGINES-001  

---

## 1. FEED ENGINE & RANKING

### Hybrid Timeline Generation
- **Following Feed**: Fetches posts strictly created by followed creators + user's own posts. Sort order: `created_at DESC` with cursor pagination.
- **Explore Ranking Algorithm**:
  $$\text{Score} = (\text{Likes} \times 1.5 + \text{Comments} \times 3.0 + 1.0) \times e^{-\lambda \cdot \Delta t}$$
  - $\Delta t$: Hours elapsed since creation.
  - $\lambda$: Decay parameter set to $0.05$.
  - Candidate pool: Latest 100 posts evaluated dynamically on the server.

### Private Account & Blocking Safeguards
- Any post authored by a private account is hidden from feeds unless the viewing user has an active, accepted follow relationship.
- Mutual blocking (`get_blocked_users`) injects an `$nin` projection ensuring neither party's posts appear in the other's feed.

---

## 2. STORIES ENGINE

### Ephemeral Lifecycle
- **Expiration Policy**: Every story is stamped with `expires_at = created_at + 24 hours`.
- **Query Protection**: All story lookups explicitly filter `{"expires_at": {"$gt": now}}` so expired stories are invisible even prior to MongoDB background TTL runner sweeps.
- **Close Friends Validation**: Stories with `is_close_friends_only=true` query the author's `social_profile.close_friends` array; viewers not in the list are filtered out before response serialization.
- **Deduplicated Views**: Atomic `$addToSet` on `viewers` prevents repeat counting from inflating view tallies.
