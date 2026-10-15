# SUPER_AI Phase 4C: Production-Quality User Accounts Implementation Plan

## 1. Objectives & Scope
- Integrate React 19 frontend with FastAPI backend and MongoDB database.
- Complete non-AI user authentication and session management (JWT access + refresh tokens, rotation, logout revocation, rate limiting).
- Real user profile management (get/update profile, display name, bio, avatar) with DB persistence.
- Real user preferences persistence (theme presets, Indic language, accessibility options, pinned/hidden modules).
- Explicit account lifecycle management (safe deletion workflow with password verification, policy for related records).
- Automated tests covering auth, profiles, preferences, security boundaries, rate limiting, and cross-user authorization.

## 2. Key Architecture Decisions
- **Token Handling**: Standard Bearer token with refresh token rotation and server-side DB blacklist/revocation in `db.refresh_tokens`. Also provide clear handling for refresh fallback.
- **Rate Limiting**: In-memory token-bucket / sliding window rate limiter in `backend/app/core/rate_limit.py` on `/auth/login` and `/auth/register` to protect against brute-force attacks without introducing heavy third-party dependencies.
- **Account Deletion**: Add `DELETE /users/me` endpoint requiring password confirmation payload. Removes user record, user preferences, conversations, notifications, and active refresh tokens, returning an explicit deletion confirmation.
- **Password Strength**: Minimum 8 characters, maximum 128 chars, requiring at least one digit and one letter.
- **Frontend Architecture**:
  - `src/context/AuthContext.tsx`: Manages `user`, `isAuthenticated`, `isLoading`, `login`, `register`, `logout`, `updateProfile`, `deleteAccount`.
  - Update `AppContext.tsx` to automatically synchronize preferences with backend on login and preference changes, falling back gracefully to `localStorage` when offline or unauthenticated.
  - `src/components/overlays/AuthModal.tsx`: Premium glassmorphism login & registration modal with validation, password toggle, error states, and loading states.
  - Update `SettingsAccountView.tsx`: Real profile edit form (display name, bio, avatar, email display), real password confirmation account deletion dialog, and logout action.
  - Update `TopBar.tsx` and `Sidebar.tsx`: Show real user profile avatar/name when authenticated, with one-click "Sign In" button when guest.
