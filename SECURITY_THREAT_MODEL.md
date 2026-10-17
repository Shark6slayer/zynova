# SUPER_AI — Security Threat Model
**Methodology:** STRIDE (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege)  
**Target:** SUPER_AI Sovereign Indic Super App (Web, Android, API, Database, Offline Engine)  
**Document Version:** 1.0 (Phase 7 Audit & Baseline)

---

## 1. System Architecture & Trust Boundaries

SUPER_AI processes multi-tenant user requests across six distinct trust zones:
1. **Zone 1: Client Runtime (Untrusted).** React 19 SPA running in untrusted mobile WebViews (Capacitor Android) and standard desktop browsers.
2. **Zone 2: Local Client Storage (Semi-Trusted).** Browser `localStorage` and `IndexedDB` (`super_ai_offline_db_v1`). Subject to physical device theft or client-side scripts.
3. **Zone 3: Network Transport (Untrusted).** Public Internet / Cellular networks. Protected via TLS 1.3 / HTTPS and WSS.
4. **Zone 4: Application Gateway & API Server (Trusted).** FastAPI ASGI backend handling authentication, authorization, business rules, and input sanitization.
5. **Zone 5: Primary Database (High Trust).** MongoDB database holding tenant accounts, posts, orders, videos, and chats.
6. **Zone 6: Local Media Storage (High Trust).** Local filesystem directory holding binary image and video chunks.

```mermaid
graph TD
    subgraph Untrusted_Zone ["Untrusted: Client & Network"]
        ClientApp["Mobile / Web App (React 19)"]
        LocalDB[("Local IndexedDB & Storage")]
        ClientApp <-->|Read / Write Drafts| LocalDB
    end

    subgraph Transport_Zone ["Transport Layer"]
        TLS["HTTPS / WSS (TLS 1.3)"]
        ClientApp <-->|Encrypted Requests| TLS
    end

    subgraph Trusted_Zone ["Trusted Application Layer"]
        FastAPI["FastAPI Backend (Uvicorn / Python 3.13)"]
        Deps["Auth & Authorization (deps.py)"]
        RateLimit["Rate Limiter (rate_limit.py)"]
        TLS <--> FastAPI
        FastAPI --> Deps
        FastAPI --> RateLimit
    end

    subgraph Data_Zone ["Data & Persistence Layer"]
        MongoDB[("MongoDB 7+ (Motor Async)")]
        MediaStorage[("Media Storage (FS Chunks)")]
        FastAPI <-->|BSON Queries| MongoDB
        FastAPI <-->|Streaming Range| MediaStorage
    end
```

---

## 2. Threat Actors Profile

| Actor Profile | Description & Capabilities | Motivation | Typical Vectors |
| :--- | :--- | :--- | :--- |
| **Opportunistic Attacker** | External Internet user with automated scanners and scripts. | Reconnaissance, data harvesting, vandalism. | Brute force login, open redirect scans, automated XSS probes, IDOR enumeration. |
| **Malicious Authenticated User** | Legitimately registered tenant attempting to access other users' data. | Financial gain, privacy breach, stalking. | BOLA parameter tampering (`video_id`, `order_id`), unauthorized API calls, fake reports. |
| **Rogue Merchant / Seller** | Onboarded seller or restaurant attempting to manipulate catalog or pricing. | Profit skimming, stock spoofing. | Client-side price tampering, fake order state transitions, inventory inflation. |
| **Local Device Attacker** | Unauthorized person with physical or root access to user's mobile device. | Session hijacking, draft theft. | Inspection of unencrypted IndexedDB, SQLite extraction, token theft from memory. |
| **Compromised Admin** | Administrator credential stolen or rogue employee. | System compromise, bulk exfiltration. | Direct database modification, log alteration, privilege escalation. |

---

## 3. Data Flow Diagrams & Threat Analysis

### 3.1 Data Flow 1: Authentication & Token Lifecycle

```mermaid
sequenceDiagram
    autonumber
    actor User as User (Client)
    participant API as FastAPI Auth (/auth)
    participant Sec as Security Core (Argon2id / JWT)
    participant DB as MongoDB (users)

    User->>API: POST /auth/login (username/email, password)
    API->>DB: find_one({username/email})
    DB-->>API: User Document (password_hash, is_active)
    API->>Sec: verify_password(plain, hash)
    Sec-->>API: Verified (Boolean)
    Note over API: Check user.is_active == True (SEC-02 Fix)
    API->>Sec: create_access_token() + create_refresh_token()
    API->>DB: update_one({$push: {refresh_tokens: token}})
    API-->>User: HTTP 200 {access_token, refresh_token, token_type}
```

#### STRIDE Analysis for Authentication:
- **Spoofing:** Attacker attempts credential stuffing or password brute force. *Mitigation:* Argon2id hashing, IP/Username rate limiting (`auth_rate_limiter`), JWT signature verification.
- **Tampering:** Attacker alters JWT claims (`sub`, `roles`). *Mitigation:* HMAC-SHA256 signature verification with secret key validation; fast-fail in production (SEC-04).
- **Repudiation:** User denies login or password change. *Mitigation:* Structured audit logging of authentication events with client IP and timestamps.
- **Information Disclosure:** Tokens or hashed passwords leaked via responses or logs. *Mitigation:* Strict Pydantic response models (`UserResponse`) redacting `password_hash` and `refresh_tokens`.
- **Denial of Service:** Massive Argon2id hash computation requests. *Mitigation:* In-flight request throttling before Argon2 evaluation.
- **Elevation of Privilege:** Deactivated user maintains access via old token. *Mitigation:* `get_current_user` enforces `is_active` check on every authenticated request (SEC-02).

---

### 3.2 Data Flow 2: Media Upload & Streaming

```mermaid
sequenceDiagram
    autonumber
    actor Creator as Content Creator
    actor Viewer as Consumer (Viewer)
    participant API as Videos API (/videos)
    participant FS as Local Storage (/storage)
    participant DB as MongoDB (videos)

    Creator->>API: POST /videos/upload (File, title, visibility)
    Note over API: 1. Validate MIME in ALLOWED_MIME_TYPES<br/>2. Read 32 bytes magic verification<br/>3. Enforce MAX_VIDEO_SIZE (100MB)
    API->>FS: Write binary chunks (UUID filename)
    API->>DB: insert_one({owner_id, storage_key, visibility})
    API-->>Creator: VideoResponse (HTTP 201)

    Viewer->>API: GET /videos/{video_id}/stream (Range: bytes=0-1048575)
    API->>DB: find_one({_id: video_id})
    Note over API: BOLA Guard (SEC-01 Fix):<br/>If visibility=='private' and owner!=viewer -> 403 Forbidden
    API->>FS: Read requested byte range
    FS-->>API: Binary stream
    API-->>Viewer: HTTP 206 Partial Content (Content-Range)
```

#### STRIDE Analysis for Media:
- **Spoofing / Tampering:** Attacker uploads executable or HTML with `.mp4` extension. *Mitigation:* Dual validation of Content-Type header AND binary magic bytes (`verify_media_magic`).
- **Information Disclosure:** Unauthenticated user accesses private video stream. *Mitigation:* Resolved via SEC-01 fix in `stream_video` enforcing owner ID comparison against `current_user`.
- **Path Traversal:** Filename manipulation (`../../etc/passwd`). *Mitigation:* All storage keys generated via server-side `uuid.uuid4().hex` + validated extension; original user filename never used as disk path.
- **Denial of Service:** Giant file upload crashing disk/RAM. *Mitigation:* Streamed chunked writing with hard ceiling of 100MB (`MAX_VIDEO_SIZE`).

---

### 3.3 Data Flow 3: Marketplace Orders & Simulated Payments

```mermaid
sequenceDiagram
    autonumber
    actor Buyer as Buyer
    participant ShopAPI as Shopping API (/shopping)
    participant PayAPI as Payments API (/payments)
    participant DB as MongoDB (products, orders)

    Buyer->>ShopAPI: POST /shopping/orders (items, idempotency_key)
    ShopAPI->>DB: Check idempotency_key uniqueness
    ShopAPI->>DB: Fetch server-side product pricing & stock
    Note over ShopAPI: Recalculate price in paise on server.<br/>Client total is NEVER trusted.
    ShopAPI->>DB: Atomic stock decrement ($inc: {stock: -qty})
    ShopAPI->>DB: Insert shopping_order (status: 'pending')
    ShopAPI-->>Buyer: OrderResponse (order_id, total_amount_paise)

    Buyer->>PayAPI: POST /payments/process (order_id, method: 'upi')
    PayAPI->>DB: Verify order ownership (customer_id == user.id)
    PayAPI->>DB: Update order status -> 'paid'
    PayAPI-->>Buyer: PaymentConfirmation (Simulated success)
```

#### STRIDE Analysis for Marketplace:
- **Tampering (Price Spoofing):** Client modifies order total from ₹1000 to ₹1 in payload. *Mitigation:* Server ignores client total and recalculates sum of `product.price_paise * item.quantity` directly from MongoDB catalog.
- **Tampering (Stock Race Condition):** Two users buy last item simultaneously. *Mitigation:* Atomic MongoDB `$inc` query with conditional filter `stock: {$gte: qty}`.
- **Repudiation (Order Replay):** Duplicate network requests generate multiple charges. *Mitigation:* Mandatory server-side `idempotency_key` indexed with unique constraint.
- **Elevation of Privilege / BOLA:** User queries or cancels order belonging to another customer. *Mitigation:* `shopping.py` restricts order retrieval strictly to `order["customer_id"] == current_user["id"]` or authorized merchant.

---

### 3.4 Data Flow 4: Offline Draft & Sync Queue

```mermaid
sequenceDiagram
    autonumber
    actor User as Mobile App User
    participant UI as React UI Component
    participant Storage as Offline Storage (IndexedDB)
    participant Sync as Sync Worker
    participant API as Backend API

    User->>UI: Create Post Draft / Edit while Offline
    UI->>Storage: savePostDraft(userId, draftData)
    Note over Storage: Multi-tenant isolation:<br/>IndexedDB key contains userId prefix
    
    User->>UI: Submit Action (Queue for sync)
    UI->>Storage: enqueueOfflineAction(userId, actionType, payload)
    
    Note over User: User switches account from Alice to Bob
    UI->>Storage: clearOfflineQueue(aliceId)
    Note over Storage: Alice actions quarantined / purged.<br/>Bob NEVER inherits Alice sync queue.

    Sync->>API: Online transition -> Dispatch queued mutations
    API-->>Sync: Mutation Confirmed (200 OK)
    Sync->>Storage: Dequeue completed item
```

#### STRIDE Analysis for Offline Engine:
- **Cross-User Data Leakage (Spoofing / Elevation):** User A logs out on shared phone; User B logs in and transmits User A's pending actions. *Mitigation:* Verified in Phase 6 offline tests: queues are partitioned by `userId`, and `OfflineSyncContext` purges/quarantines queues upon account switch.
- **Tampering (Duplicate Orders):** User queues order or payment while offline and replays when reconnected. *Mitigation:* Order creation and payment processing are explicitly prohibited from offline enqueueing (`isActionQueuable` check).
- **Information Disclosure:** Unencrypted drafts in IndexedDB. *Mitigation:* Addressed in documentation (SEC-08); application clears sensitive cached data on explicit logout.

---

### 3.5 Data Flow 5: Real-time WebSocket Chat

```mermaid
sequenceDiagram
    autonumber
    actor ClientA as Alice
    actor ClientB as Bob
    participant WS as WebSocket Manager (ws_manager.py)
    participant DB as MongoDB (conversations, messages)

    ClientA->>WS: WS /chat/ws?token={access_token}
    WS->>WS: Decode & verify JWT token
    WS->>DB: Verify Alice is active user
    WS-->>ClientA: Connection Accepted

    ClientA->>WS: Send JSON {room_id: "room_ab", content: "Hello"}
    WS->>DB: Verify Alice is a participant in room_ab
    Note over WS: If Alice not in room -> Reject message with 403 error
    WS->>DB: Persist message in messages collection
    WS->>ClientB: Forward message frame to Bob's active socket
```

#### STRIDE Analysis for WebSockets:
- **Spoofing:** Attacker connects to WebSocket without credentials. *Mitigation:* Mandatory token handshake query parameter decoded before connection acceptance.
- **Information Disclosure (Eavesdropping):** Attacker joins arbitrary room ID to spy on conversations. *Mitigation:* `ws_manager.py` verifies caller ID against conversation `participants` array before routing messages.
- **Denial of Service (Connection Exhaustion):** Attacker opens thousands of concurrent sockets. *Mitigation:* Per-user connection cap enforced by WebSocket manager.

---

## 4. STRIDE Threat Catalog & Mitigation Matrix

| Threat Category | Threat Description | Vulnerable Scenario | Implemented Mitigation | Residual Risk |
| :--- | :--- | :--- | :--- | :--- |
| **Spoofing** | Forged JWT access token. | Attacker attempts to forge token using default development secret. | SEC-04: Lifespan enforces non-default key in production. Argon2id for password verification. | Low (Secret key security dependent on operational hygiene). |
| **Spoofing** | WebSocket unauthorized connection. | Malicious client attempts socket connection without credentials. | JWT token required on query parameter and validated on connection. | Low (Ephemeral token param in URL; recommend header/cookie in Phase 8). |
| **Tampering** | File upload payload disguise. | Malicious script uploaded disguised as PNG/MP4. | Binary magic bytes and MIME validation enforced in `social.py` and `videos.py`. | Low (Advanced polyglot files; recommend ClamAV in Phase 8). |
| **Tampering** | Client-side price tampering. | Malicious buyer alters item price in order request. | Server ignores client amount and recalculates total from catalog. | None (Enforced server-side). |
| **Repudiation** | Replayed order or charge. | Network latency triggers duplicate submission. | Server-side idempotency keys with unique indexes. | None. |
| **Information Disclosure** | BOLA on private video streaming. | Attacker accesses private video URL directly. | SEC-01: Ownership check enforced in `stream_video`. | None. |
| **Information Disclosure** | Deactivated user accesses profile. | Soft-deleted user token remains valid. | SEC-02: `is_active` checked on every authenticated request. | None. |
| **Denial of Service** | Social post / comment spam. | Automated bot spams posts and comments. | Rate limiters (`rate_limit.py`) enforce limits per user ID. | Medium (In-memory limiter per process; Phase 8 Redis required). |
| **Elevation of Privilege** | Normal user accesses seller/admin controls. | Regular user submits seller-only product updates. | Strict role-based and ownership checks on seller endpoints. | None. |

---

## 5. Security Conclusions

The SUPER_AI architecture adheres to defense-in-depth principles across its core subsystems. The threat model confirms that the primary attack surfaces (BOLA on streaming, deactivated user token validity, client-side price tampering, and offline queue contamination) are either fully remediated or bounded by existing server-side controls.
