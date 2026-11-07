# PHASE 28 — CROSS-PLATFORM CONTENT SHARING SPECIFICATION

## 1. Overview
The Zynova Cross-Platform Sharing gateway enables friction-free sharing of public content across web, mobile, and third-party messaging apps with uniform metadata resolution and deep linking.

---

## 2. Share Resolution Endpoint (`GET /api/v1/platform/share/{content_type}/{content_id}`)

### Supported Content Types:
- `post`: Public social updates (`/post/{id}`)
- `reel`: Public short-form video reels (`/reels/{id}`)
- `video`: Landscape long-form video (`/videos/{id}`)
- `short`: Vertical video shorts (`/shorts/{id}`)
- `channel`: Creator channel profiles (`/channel/{handle}`)
- `profile`: User public identity (`/profile/{id}`)
- `community`: Public group community hubs (`/communities/{id}`)

### Response Schema:
```json
{
  "share_url": "https://zynova.intellidev.in/videos/67cda...81",
  "content_type": "video",
  "title": "Quantum Computing Masterclass",
  "description": "Learn quantum states and gates.",
  "thumbnail_url": "https://cdn.zynova.net/thumbnails/qc.jpg",
  "deep_link": "/videos/67cda...81",
  "is_public": true,
  "author_name": "Tech Studio"
}
```

---

## 3. Security & Access Boundaries
1. **Private Video Guard**: Private videos return `403 Forbidden` if requested by an unauthorized caller.
2. **Mutual Block Isolation**: If the viewer and author have a block relationship, the share endpoint strictly returns `403 Forbidden`.
3. **Private Communities**: Private communities return `403 Forbidden` unless the authenticated user is an existing member or admin.
4. **Deleted Content Fallback**: Missing or deleted assets consistently yield `404 Not Found`.
