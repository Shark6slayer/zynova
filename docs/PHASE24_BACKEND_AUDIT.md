# PHASE 24 — BACKEND ARCHITECTURAL AUDIT & DEPENDENCY MAP

**Document Reference:** `ZYNOVA-DOC-PHASE24-AUDIT`  
**Execution Timestamp:** 2026-11-07T10:39:00+05:30  
**Evaluator:** Principal Backend Architect & Distributed Systems Engineer  

---

## 1. BACKEND DIRECTORY TOPOLOGY & COMPONENT INVENTORY

The existing backend is structured as an asynchronous modular monolith built on **FastAPI 0.115.11** running on **CPython 3.13.15** with async database operations backed by **Motor 3.7.0 / PyMongo 4.11.2** and cryptographic anchoring via **cryptography 44.0.2** and **Argon2id**.

```
backend/app/
├── api/
│   ├── deps.py               # JWT bearer validation & current_user injection
│   ├── router.py             # Top-level API router mounting 16 route domains
│   └── routes/               # API route controllers
│       ├── ai.py             # AI Core Engine (SSE token streaming, models catalog, threads)
│       ├── auth.py           # Register, login, refresh, logout, token blacklist
│       ├── chat.py           # Real-time WebSocket & REST chat messaging
│       ├── conversations.py  # User conversation threads
│       ├── devices.py        # Ed25519 challenge-response device binding
│       ├── food.py           # Dining discovery, restaurants, food orders
│       ├── health.py         # /health, /ready, /version, /health/security
│       ├── ledger.py         # Ed25519 cryptographic audit ledger inspection
│       ├── notifications.py  # Event-driven in-app notifications
│       ├── payments.py       # UPI / RuPay sandbox simulator
│       ├── preferences.py    # 22 Scheduled Indian languages preferences
│       ├── search.py         # Multi-entity universal search
│       ├── shopping.py       # Marketplace catalog & seller inventory
│       ├── social.py         # Feed posts, likes, user reporting, media scan
│       ├── users.py          # User profile settings & account deletion
│       └── videos.py         # Video metadata, public feed, private streaming
├── core/
│   ├── ai_errors.py          # Standardized normalized AI error taxonomy
│   ├── audit_ledger.py       # Ed25519 SHA-256 hash-chained event ledger
│   ├── blockchain_anchor.py  # Zero-PII state commitment anchoring
│   ├── config.py             # Pydantic Settings & environment variables
│   ├── crypto_kms.py         # AES-256-GCM envelope encryption with HKDF
│   ├── rate_limit.py         # In-memory sliding window rate limiter
│   ├── scanner.py            # Stream malware scanner (ClamAV TCP + EICAR)
│   ├── security.py           # Argon2id password hashing & JWT encoding
│   ├── security_logger.py    # Structured security event logger
│   ├── token_revocation.py   # In-memory JTI revocation cache
│   └── ws_manager.py         # Real-time WebSocket connection manager
├── database/
│   └── client.py             # Motor async MongoDB client & ping health check
├── schemas/
│   └── all_schemas.py        # Comprehensive Pydantic models for all entities
└── services/
    ├── ai_engine_service.py  # AI Core Engine orchestration & prompt assembly
    ├── ai_providers.py       # BaseAIProvider, Gemini, OpenAI, Claude, Mock
    ├── ai_smoke_validator.py # Opt-in provider smoke validator
    ├── marketplace_reconciliation.py # Paired ledger reconciliation for marketplace
    ├── notification_service.py       # Server-side event notification dispatcher
    └── payment_provider.py           # Sandbox payment engine
```

---

## 2. DATABASE COLLECTIONS & INDEXING STATUS

The active MongoDB database (`zynova_db` / `super_ai_db`) hosts the following primary collections:

| Collection Name | Primary Identifier | Key Fields & Indexes | Usage Domain |
| :--- | :--- | :--- | :--- |
| `users` | `_id: ObjectId` | `email` (unique), `username` (unique), `created_at` | Unified Identity |
| `user_preferences` | `_id: ObjectId` | `user_id` (unique), `language` | Indic Localization |
| `device_sessions` | `_id: ObjectId` | `user_id`, `device_id`, `public_key` | Device Binding |
| `token_revocations` | `_id: ObjectId` | `jti` (unique, TTL index) | Security Revocation |
| `posts` | `_id: ObjectId` | `user_id`, `created_at`, `tags` | Social Platform |
| `comments` | `_id: ObjectId` | `post_id`, `user_id`, `created_at` | Social Platform |
| `reports` | `_id: ObjectId` | `reporter_user_id`, `target_id` | Moderation & Safety |
| `conversations` | `id: str` | `participants`, `updated_at` | Connect Messaging |
| `messages` | `id: str` | `conversation_id`, `sender_id`, `created_at` | Connect Messaging |
| `videos` | `_id: ObjectId` | `creator_user_id`, `is_public`, `created_at` | Video Platform |
| `notifications` | `_id: ObjectId` | `user_id`, `read`, `created_at`, `event_id` | Shared Alerts |
| `audit_ledger` | `_id: ObjectId` | `sequence` (unique), `current_hash`, `prev_hash` | Sovereign Ledger |
| `ai_conversations` | `id: str` | `user_id`, `updated_at` | AI Core Engine |

---

## 3. INFRASTRUCTURE CAPABILITY MAP & GAPS

1. **Redis Integration:**
   - **Current State:** `settings.REDIS_URL` is declared in `config.py`, but sliding-window rate limiters and token revocation run in local process memory fallback.
   - **Target Phase 24 Adoption:** Redis connection pooling will back distributed WebSocket pub/sub and cross-worker rate limiting.
2. **WebSocket & Real-Time Signaling:**
   - **Current State:** `ConnectionManager` in `backend/app/core/ws_manager.py` manages in-memory WebSocket connections per user ID.
   - **Target Phase 24 Adoption:** Extends to support WebRTC call signaling frames (`offer`, `answer`, `ice_candidate`) and typing indicators.
3. **Media Storage:**
   - **Current State:** Media files upload directly to local disk with EICAR stream scanning (`scanner.py`).
   - **Target Phase 24 Adoption:** Transition to secure presigned upload authorization protocol supporting S3 / Cloudflare R2 object storage.
4. **Background Jobs & Worker Queue:**
   - **Current State:** Lightweight background tasks use FastAPI `BackgroundTasks`. Heavy video transcoding is currently synchronous.
   - **Target Phase 24 Adoption:** Decoupled asynchronous video processing pipeline utilizing FFmpeg.
