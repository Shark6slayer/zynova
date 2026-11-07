# ZYNOVA 3.0 — PHASE 25: API REFERENCE
**Document ID:** DOC-PHASE25-API-001  
**Prefix:** `/api/v1/social`  

---

## 1. PROFILES & RELATIONSHIPS

- `GET /social/profiles/{user_id}`: Fetch user's social profile. Enforces mutual blocking (returns 404).
- `POST /social/profiles/{user_id}/follow`: Follow user or submit request if private.
- `DELETE /social/profiles/{user_id}/follow`: Unfollow user.
- `POST /social/follow-requests/{sender_id}/respond?action=accept|reject`: Respond to pending request.
- `DELETE /social/followers/{follower_id}`: Remove follower from own profile.
- `GET /social/suggested`: List recommended creator accounts.

---

## 2. POSTS & FEED

- `POST /social/posts`: Create post (supports carousels up to 10 assets, hashtags, locations).
- `GET /social/feed?mode=discovery|following|reels&limit=25&before=<iso>`: Paginated home feed.
- `GET /social/users/{user_id}/posts`: User posts grid (private accounts protected).
- `PATCH /social/posts/{post_id}`: Edit own post.
- `DELETE /social/posts/{post_id}`: Delete own post.
- `POST /social/posts/{post_id}/like`: Toggle like on post.
- `POST /social/posts/{post_id}/comments`: Post comment or reply.
- `DELETE /social/comments/{comment_id}`: Delete comment (owner or post author).
- `POST /social/posts/{post_id}/bookmark`: Save/bookmark post.
- `GET /social/bookmarks`: Retrieve bookmarked posts.

---

## 3. STORIES & HIGHLIGHTS

- `POST /social/stories`: Post 24-hour ephemeral story (media_url, caption, close friends only).
- `GET /social/stories/feed`: Active story tray grouped by followed accounts.
- `POST /social/stories/{story_id}/view`: Record unique story view.
- `POST /social/stories/{story_id}/react`: Add emoji reaction.
- `GET /social/stories/{story_id}/viewers`: Viewers directory (author only).
- `POST /social/highlights`: Create story highlight collection.
- `GET /social/users/{user_id}/highlights`: List user's highlights.

---

## 4. NOTES & EXPLORE

- `POST /social/notes`: Post 60-character note with music metadata.
- `GET /social/notes`: Retrieve notes from followed accounts.
- `GET /social/explore`: Algorithmic explore discovery feed.
- `GET /social/tags/{tag}`: Filter posts by hashtag.

---

## 5. VERIFIED BADGE WORKFLOW

- `POST /social/verification/apply`: Submit identity evidence for review.
- `POST /social/verification/{app_id}/review?action=approve|reject`: Admin review endpoint.
