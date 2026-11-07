# ZYNOVA 3.0 — PHASE 25: SOCIAL ARCHITECTURE SPECIFICATION
**Document ID:** DOC-PHASE25-ARCH-001  
**Module:** Zynova Social Platform (Instagram-Inspired)  
**Status:** Implemented & Verified  

---

## 1. ARCHITECTURAL TOPOLOGY

Zynova Social integrates seamlessly into the unified identity and storage infrastructure delivered in Phase 24.1:

```
[Web / Mobile Client]
         │
         ├── REST API: /api/v1/social/* (Posts, Stories, Reels, Explore, Profiles)
         ├── WebSocket: wss://.../ws (Live story badges, interactions, receipts)
         └── Direct S3/R2 Ingestion: Presigned media uploads
                  │
                  ▼
         [FastAPI Application Server]
                  │
                  ├── social_service.py (Domain Logic: Ranking, TTL, Filtering)
                  ├── identity_service.py (Unified Profiles, Mutual Blocking)
                  ├── enhanced_ws_manager.py (EventBus Dispatch)
                  └── scanner.py (Malware Quarantine & Verification)
                  │
                  ▼
         [MongoDB Atlas Storage Engine]
                  ├── users (Embedded social_profile, followers, verified badge)
                  ├── posts (Carousels, tags, locations, likes, comment counts)
                  ├── post_comments (Comments tree)
                  ├── social_stories (24h TTL index, viewers array)
                  ├── story_highlights (Permanent curated collections)
                  ├── social_notes (60-char text status, 24h lifespan)
                  ├── social_interactions (Bookmarks, reactions)
                  └── verification_applications (Review queue)
```

---

## 2. CORE DOMAIN MODULES

1. **Social Identity**: Single account with public/private settings, verified badge status, bio, website, and mutual blocking.
2. **Feed Engine**: Following timeline + engagement-decay discovery with cursor-based pagination.
3. **Stories Engine**: 24-hour ephemeral visual moments, close friends restriction, and view tracking.
4. **Reels Vertical Stream**: Vertical video stream with background audio, likes, comments, and creator navigation.
5. **Follow Graphs**: Automatic follows for public accounts, follow requests with accept/reject for private accounts.
6. **Explore Discovery**: Real-time trending ranking with exponential time decay.
7. **Social Notes**: 24-hour status snippets with music metadata.
8. **Verification Workflow**: Formal document submission and reviewer queue.
