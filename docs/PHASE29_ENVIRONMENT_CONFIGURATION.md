# PHASE 29 — ENVIRONMENT CONFIGURATION & SECRET STRATEGY

## 1. Environment Separation Strategy
Zynova recognizes three execution environments:
- `development`: Local development with SQLite/local-Mongo, in-memory rate limiting, and optional mock AI.
- `staging`: Replica of production connected to staging MongoDB Atlas and staging Redis.
- `production`: Strict security validation: default secrets prohibited, debug disabled, CORS restricted.

---

## 2. Production Environment Variable Reference

| Variable Name | Required | Default in Prod | Description / Secret Classification |
| :--- | :--- | :--- | :--- |
| `ENVIRONMENT` | Yes | `"production"` | Operating environment (`development`, `staging`, `production`) |
| `APP_NAME` | No | `"ZYNOVA_BACKEND"` | Identifying service name |
| `DEBUG` | Yes | `false` | Disables debug stack traces in HTTP responses |
| `MONGODB_URI` | Yes | *None (Must set)* | MongoDB Atlas connection string with TLS & credentials |
| `MONGODB_DB_NAME` | Yes | `"zynova_db"` | Primary database name |
| `JWT_SECRET_KEY` | Yes | *None (Must set)* | 256-bit cryptographically secure string (Fails startup if default) |
| `JWT_ALGORITHM` | No | `"HS256"` | JWT signature algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | No | `30` | Access token lifespan |
| `REFRESH_TOKEN_EXPIRE_DAYS` | No | `14` | Refresh token lifespan |
| `CORS_ORIGINS` | Yes | Allowed domains | JSON list of trusted origins (`https://zynova.intellidev.in`) |
| `REDIS_URL` | Staging/Prod | *None* | `rediss://...` for multi-worker distributed rate limiting & WS bus |
| `RATE_LIMIT_FAIL_CLOSED_IN_PROD` | Yes | `true` | If true, rejects sensitive auth if Redis drops in production |
| `MASTER_ENCRYPTION_KEY` | Yes | *32-byte key* | AES-256 master key for database field encryption (PII) |
| `ACTIVE_KEY_VERSION` | No | `"v1"` | Active version tag for envelope encryption rotation |
| `AI_MOCK_MODE` | Yes | `false` | Hard disabled in production to guarantee real inference |
| `AI_DEFAULT_PROVIDER` | Yes | `"gemini"` | Default LLM provider |
| `GEMINI_API_KEY` | Conditional | *Secret* | Google Gemini API key (Server-side only) |
| `OPENAI_API_KEY` | Conditional | *Secret* | OpenAI API key (Server-side only) |
| `ANTHROPIC_API_KEY` | Conditional | *Secret* | Anthropic Claude API key (Server-side only) |
| `MEDIA_S3_ACCESS_KEY_ID` | Optional | *Secret* | Cloudflare R2 / AWS S3 key ID |
| `MEDIA_S3_SECRET_ACCESS_KEY` | Optional | *Secret* | Cloudflare R2 / AWS S3 secret |
| `MEDIA_S3_BUCKET` | Optional | *Bucket Name* | Target media storage bucket |
| `MEDIA_CDN_BASE_URL` | Optional | *URL* | Base CDN URL for cached delivery |

---

## 3. Secret Rotation & Hygiene
- **Zero Secrets in Frontend**: `GEMINI_API_KEY`, `OPENAI_API_KEY`, and S3 credentials are strictly read on the backend. Frontend clients only interact through authenticated proxy endpoints (`/api/v1/ai/chat`, `/api/v1/platform/media/upload`).
- **Key Rotation**: Cryptographic fields use envelope tags (`enc:v1:...`). Calling `rotate_field_encryption(enc_str, target_version="v2")` re-encrypts stored ciphertext in-place without data loss.
