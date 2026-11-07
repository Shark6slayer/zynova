# PHASE 28 — DEEP LINKS & ROUTING SPECIFICATION

## 1. Overview
Zynova establishes a deterministic deep-link structure compatible with web browsers, Android App Links, and Capacitor mobile wrappers.

---

## 2. Canonical Route Directory

| Resource Type | Canonical Web Route | Android App Link Pattern | Fallback / Auth Required |
| :--- | :--- | :--- | :--- |
| User Profile | `#/profile/{user_id_or_username}` | `https://zynova.intellidev.in/profile/*` | Public / Guest viewable |
| Social Post | `#/post/{post_id}` | `https://zynova.intellidev.in/post/*` | Public / 404 on deleted |
| Social Reel | `#/reels/{reel_id}` | `https://zynova.intellidev.in/reels/*` | Public / 404 on deleted |
| Direct Chat | `#/chat/{conversation_id}` | `https://zynova.intellidev.in/chat/*` | Auth Required (Redirects to Login) |
| Community | `#/communities/{community_id}` | `https://zynova.intellidev.in/communities/*`| Auth Required for private |
| Long-form Video| `#/videos/{video_id}` | `https://zynova.intellidev.in/videos/*` | Public / 403 on private |
| Vertical Short| `#/shorts/{video_id}` | `https://zynova.intellidev.in/shorts/*` | Public |
| Creator Channel| `#/channel/{handle}` | `https://zynova.intellidev.in/channel/*`| Public |

---

## 3. Client Route Resolution Engine
The client `AppContext` listens to `hashchange` and `popstate` events to:
- Instantly mount the designated module without requiring full-page reloads.
- Synchronize browser history states (`pushState`).
- Intercept unauthorized private routes and display non-destructive auth modals.
