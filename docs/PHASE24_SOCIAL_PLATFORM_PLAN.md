# ZYNOVA 3.0 — PHASE 24: SOCIAL PLATFORM ARCHITECTURE PLAN
**Document ID:** DOC-PHASE24-SOCIAL-001  
**Author:** Principal Social Platform Architect & Senior Full-Stack Engineer  
**Status:** Approved Technical Plan  
**Module:** Zynova Social (Instagram-Inspired Experience)  

---

## 1. PRODUCT SPECIFICATION & VISION

**Zynova Social** delivers a visually immersive, mobile-first social networking experience focusing on visual expression, community discovery, and short-form storytelling:
1. **User Profiles**: Rich bios, follower/following counts, profile pictures, highlight reels, and grid views of posts and reels.
2. **Chronological & Ranked Feed**: Home feed blending media from followed users with personalized discovery algorithms.
3. **Posts**: Multi-photo carousels (up to 10 images/videos) with aspect ratio support (1:1, 4:5, 16:9), captions, hashtags, and location tags.
4. **Reels**: 9:16 vertical short-form video feed with continuous gesture-driven scrolling, background audio tracks, and instant reaction badges.
5. **Stories**: Ephemeral 24-hour visual moments with automatic MongoDB TTL expiration, viewer tracking, and interactive reaction stickers.
6. **Social Interactions**: Double-tap to like, nested comments with replies, save to bookmarks, and direct sharing to Zynova Connect.
7. **Explore & Hashtags**: Search and discovery grid categorized by trending hashtags, popular creators, and personalized recommendations.

---

## 2. API ROUTE TAXONOMY & CONTRACTS

Prefix: `/api/v1/social`

### 2.1 Profiles & Relationships
- `GET /social/profiles/{username}`: Fetch public or relationship-bounded social profile.
- `PATCH /social/profiles/me`: Update bio, website, avatar, and privacy toggle (`is_private`).
- `POST /social/users/{user_id}/follow`: Follow/request follow.
- `DELETE /social/users/{user_id}/unfollow`: Unfollow user.
- `GET /social/users/{user_id}/followers`: Paginated list of followers.
- `GET /social/users/{user_id}/following`: Paginated list of following.

### 2.2 Feed & Posts
- `GET /social/feed`: Paginated timeline feed (cursor-based using post `created_at` and `_id`).
- `POST /social/posts`: Create post (references verified `media_assets` IDs, caption, tags).
- `GET /social/posts/{post_id}`: Retrieve single post with author details.
- `DELETE /social/posts/{post_id}`: Delete own post.
- `POST /social/posts/{post_id}/like`: Toggle like on post.
- `GET /social/posts/{post_id}/comments`: Fetch comments tree.
- `POST /social/posts/{post_id}/comments`: Post a comment or reply (`parent_comment_id`).

### 2.3 Reels & Stories
- `GET /social/reels/feed`: Vertical infinite-scroll reel stream optimized for low-latency playback.
- `POST /social/stories`: Create 24-hour ephemeral story.
- `GET /social/stories/feed`: Active story tray organized by followed users with unread indicators.
- `GET /social/stories/{story_id}/viewers`: Viewers list for author.

### 2.4 Explore & Hashtags
- `GET /social/explore`: Masonry grid of trending posts and reels.
- `GET /social/tags/{tag}`: Posts tagged with specific hashtag.

---

## 3. FEED GENERATION & RANKING ALGORITHM

To prevent database bottlenecking on high-fanout accounts, Zynova employs a **Hybrid Fan-Out Strategy**:

```
[User Follows < 2,000 Accounts] ──► Fan-Out on Write:
                                    Post IDs pushed to active followers' Redis feed cache:
                                    `zynova:feed:user:{follower_id}` (Sorted Set scored by timestamp)

[Celebrity / High-Fanout (> 2,000)] ──► Fan-Out on Read:
                                       Posts queried dynamically at read time and merged
                                       with user's cached timeline.
```

### Feed Scoring Formula:
$$\text{Score} = (\text{Likes} \times 1.5 + \text{Comments} \times 3.0 + \text{Shares} \times 5.0) \times e^{-\lambda \cdot \Delta t}$$
Where $\Delta t$ represents hours elapsed since post creation and $\lambda$ is a decay coefficient ($\lambda = 0.05$), ensuring fresh content ranks prominently while preserving high-engagement community highlights.

---

## 4. DATABASE INTEGRATION & INDEXING HIGHLIGHTS

References schemas in `docs/PHASE24_DATABASE_ARCHITECTURE.md`:
- `social_posts`: Indexed by `[("author_id", 1), ("created_at", -1)]`, `[("tags", 1), ("created_at", -1)]`.
- `social_stories`: TTL index on `expires_at` (`expireAfterSeconds=0`) guarantees zero orphaned ephemeral media.
- `social_interactions`: Unique compound index on `[("user_id", 1), ("target_type", 1), ("target_id", 1), ("interaction_type", 1)]` prevents duplicate likes or bookmarks.
