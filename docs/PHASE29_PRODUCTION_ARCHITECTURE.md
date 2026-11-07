# PHASE 29 — PRODUCTION ARCHITECTURE SPECIFICATION

## 1. Production Topology & Component Map

Zynova's production runtime architecture organizes compute, database, real-time messaging, AI inference, and media delivery across validated boundaries:

```
                          Internet Users (Web / Mobile Android)
                                            │
                        HTTPS / WSS (Cloudflare CDN / DNS)
                                            │
                     ┌──────────────────────┴──────────────────────┐
                     │                                             │
             Static Frontend                                Backend API & WSS
        https://zynova.intellidev.in                   https://zynova-backend.onrender.com
        (React 19 + Vite + Tailwind)                  (FastAPI + Uvicorn + Motor)
                     │                                             │
                     └──────────────────────┬──────────────────────┘
                                            │
                 ┌──────────────────────────┼──────────────────────────┐
                 ▼                          ▼                          ▼
       [MongoDB Atlas Cluster]       [Upstash / Redis]       [Cloudflare R2 / S3]
        - TLS 1.3 + Certifi CA       - Rate limiting          - Presigned direct upload
        - Replica Set (M0/M10)       - Pub/Sub event bus      - Range-request streaming
        - Compound Indexes           - Multi-worker sessions  - MIME magic-byte scan
                 │                          │                          │
                 └──────────────────────────┼──────────────────────────┘
                                            │
                                            ▼
                               [Multi-Provider AI Core]
                                - Google Gemini API
                                - OpenAI / Anthropic APIs
                                - Zero client secret exposure
```

---

## 2. Infrastructure Dependency & Status Classification

| Dependency / Layer | Implementation Asset | Operational Status | Production Readiness Category |
| :--- | :--- | :--- | :--- |
| **Frontend Hosting** | Cloudflare Pages / Static CDN | Verified | **OPERATIONAL** |
| **Backend API Server** | Render PaaS (`render.yaml`, FastAPI) | Verified | **OPERATIONAL** |
| **Primary Database** | MongoDB Atlas (`zynova_db`, Motor) | Verified (TLS) | **OPERATIONAL** |
| **Rate Limiter Cache**| In-memory sliding window + Redis adapter | Verified fallback | **OPERATIONAL (Degraded without live Redis)** |
| **WebSocket Event Bus**| In-memory bus / `RedisEventBus` | Verified fallback | **OPERATIONAL (Single-instance ready)** |
| **Media Storage** | Local dev storage / Cloudflare R2 | Verified local & R2 code | **OPERATIONAL** |
| **AI Core Engine** | Gemini / OpenAI / Anthropic abstractions | Verified multi-provider | **OPERATIONAL (Requires API keys)** |
| **Android App** | Capacitor Android (`compileSdk=36`) | Built (`.apk`) | **CONFIGURED (No active physical device)** |
| **Audit Logging** | Ed25519 Cryptographic Hash Ledger | Verified | **OPERATIONAL** |
| **Malware Scanning** | ClamAV TCP Stream Scanner | Verified local fallback | **CONFIGURED (Requires clamd daemon in prod)** |

---

## 3. Single Points of Failure (SPOF) Analysis & Mitigations
1. **Single Backend Instance**: Render free/starter tiers run a single container. Mitigation: Stateless API design allows instant horizontal scaling behind a load balancer when `REDIS_URL` is populated.
2. **Redis Outage**: If Redis goes down, `RateLimiter` fails open for general traffic, but fails closed on sensitive endpoints (`login`, `register`, `password reset`) in production to prevent credential brute-forcing.
3. **External AI Outage**: AI Engine implements graceful error formatting (`AIProviderException`) and status 503 fallback without taking down primary platform operations.
