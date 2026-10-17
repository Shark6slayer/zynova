# 05 — TECHNICAL ARCHITECTURE SPECIFICATION

A comprehensive engineering breakdown of SUPER_AI's full-stack architecture, runtime boundaries, communication protocols, and cryptographic subsystems.

---

## 1. High-Level System Architecture

```mermaid
graph TB
    subgraph Client Layer
        Web[React 19 + Vite Web Application]
        Mobile[Capacitor 8.1.2 Native Android App]
        IDB[(IndexedDB Offline Cache & Queue)]
    end

    subgraph Edge & API Gateway
        Nginx[Nginx Reverse Proxy / SSL Termination]
        RateLimit[Shared Rate Limiter & Token Blacklist]
    end

    subgraph Application Core (FastAPI / Python 3.13)
        AuthService[Auth & Session Service]
        ChatService[Realtime WebSocket Chat]
        MarketService[Zaviro Marketplace & Food]
        CryptoService[AES-256-GCM Envelope KMS]
        LedgerService[RFC 8785 Audit Ledger]
    end

    subgraph Persistence & External Verification
        Mongo[(Authoritative MongoDB 7+)]
        Redis[(Optional Distributed Redis Cache)]
        EVMNode[Local / Testnet EVM Blockchain Node]
    end

    Web <-->|HTTPS / WSS| Nginx
    Mobile <-->|HTTPS / WSS| Nginx
    Web <--> IDB
    Mobile <--> IDB

    Nginx --> RateLimit
    RateLimit --> AuthService
    RateLimit --> ChatService
    RateLimit --> MarketService

    AuthService --> Mongo
    ChatService --> CryptoService
    CryptoService --> Mongo
    MarketService --> LedgerService
    LedgerService --> Mongo
    LedgerService -.->|Periodic Checkpoints| EVMNode
    RateLimit -.-> Redis
```

---

## 2. Technology Stack Breakdown

### 2.1 Client Runtime
- **Framework:** React 19.0.0 utilizing functional components and modern React Hooks (`useCallback`, `useMemo`, `useRef`).
- **Language:** TypeScript 5.8 (Strict type checking enabled, zero implicit `any`).
- **Bundler:** Vite 8.3.4 (Compiles full production distribution in 838ms).
- **Styling Architecture:** Pure Vanilla CSS with CSS custom properties (tokens for colors, elevation, transitions, and typography).
- **Mobile Container:** Capacitor 8.1.2 targeting Android API Level 36 (Java 21, Gradle 8.13).

### 2.2 Backend Runtime
- **Application Server:** FastAPI 0.115 running asynchronously on Python 3.13.
- **ASGI Server:** Uvicorn with multiple asynchronous worker support.
- **Validation Engine:** Pydantic v2 for strict schema parsing, payload serialization, and type safety.
- **Database Driver:** Motor (asyncio wrapper around PyMongo) for non-blocking database queries.

### 2.3 Persistence & Storage Engine
- **Primary Database:** MongoDB 7.0 Community/Enterprise.
- **Consistency Model:** Strong consistency on individual document updates using atomic conditional operators (`$inc`, `$set`, `$push`).
- **Offline Storage:** Browser/Webview IndexedDB featuring 3 dedicated object stores: `post_drafts`, `public_cache`, and `action_queue`.

---

## 3. Cryptographic Subsystem Architecture

### 3.1 Envelope Encryption at Rest
To protect sensitive user communications (chat messages, private notes) without relying solely on storage-volume encryption:
- **Master Key (KEK):** 256-bit key managed with version tags (`v1`, `v2`).
- **Data Encryption Key (DEK):** Derived uniquely per document using HKDF-SHA256 with context binding:
  $$\text{DEK} = \text{HKDF}(\text{IKM}=\text{MasterKey}, \text{Salt}=\text{Nonce}, \text{Info}=\text{"entity\_type:entity\_id"})$$
- **Payload Encryption:** AES-256-GCM generating a 128-bit authentication tag.
- **Transplant Defense:** If an attacker moves ciphertext from message A to message B, decryption fails because the `info` context does not match.

### 3.2 Private Audit Ledger
- **Serialization:** Strict RFC 8785 JSON Canonicalization Scheme (JCS).
- **Chaining:** Every event $E_n$ contains the cryptographic hash of event $E_{n-1}$:
  $$\text{Hash}_n = \text{SHA-256}(\text{JCS}(E_n.\text{payload} \parallel \text{Hash}_{n-1}))$$
- **Checkpointing:** Every 100 events, a checkpoint is generated containing the sequence range and Merkle root, signed with an Ed25519 private key.

### 3.3 Hybrid Blockchain Anchoring
- **Contract:** `SuperAIAuditLedgerAnchor.sol` deployed on an EVM-compatible node.
- **Zero-PII Footprint:** Only the sequence number, timestamp, and 32-byte checkpoint hash are anchored on-chain. Zero personal user data or message contents ever touch the blockchain.

---

## 4. Mobile Runtime & Security Posture
- **Application ID:** `com.superai.app`
- **Network Security:** `android:usesCleartextTraffic="false"` explicitly enforced in `AndroidManifest.xml`.
- **WebView Hardening:** File access disabled (`setAllowFileAccess(false)`), content access disabled, geolocation permissions guarded by native runtime prompts.
- **Build Evidence:** Debug APK compiled successfully: `android/app/build/outputs/apk/debug/app-debug.apk` (14.2 MB).
