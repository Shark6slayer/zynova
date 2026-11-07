# PHASE 28 — GLOBAL SEARCH ENGINE SPECIFICATION

## 1. Overview
The Zynova Unified Search Engine (`GET /api/v1/search`) consolidates discovery across all platforms into a single indexed query interface without duplicating data stores.

---

## 2. Search Categories & Targets

| Category Filter | Indexed Collections | Matching Fields | Privacy & Access Controls |
| :--- | :--- | :--- | :--- |
| `people` | `users` | `username`, `full_name`, `bio` | Active users only (`is_active: true`); mutual blocks excluded. |
| `posts` | `posts` | `content`, `author_username`, `author_full_name` | Public posts only; author blocking applied. |
| `reels` | `posts` (`media_type="video"`) | `content`, `author_username` | Public vertical reels only; author blocking applied. |
| `videos` | `videos` (`is_short=false`) | `title`, `description`, `category`, `channel_name` | `visibility: "public"`; owner blocking applied. |
| `shorts` | `videos` (`is_short=true`) | `title`, `description`, `audio_title` | `visibility: "public"`; owner blocking applied. |
| `channels` | `creator_channels` | `name`, `handle`, `description` | Public channels; owner blocking applied. |
| `communities`| `connect_communities` | `name`, `description` | Public communities or caller is verified member/admin. |
| `hashtags` | `posts.tags` | `#<tag>` prefix | Aggregated public tagged posts. |

---

## 3. Search History Management
Authenticated users maintain a private search history stored in `db.search_history`:
- Logged automatically during search query execution.
- Retrieved via `GET /api/v1/search/history?limit=20`.
- Individual deletion via `DELETE /api/v1/search/history/{id}`.
- Global purge via `DELETE /api/v1/search/history`.
