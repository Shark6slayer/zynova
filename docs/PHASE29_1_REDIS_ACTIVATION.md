# PHASE 29.1 — REDIS ACTIVATION & STAGING CONFIGURATION

## 1. Overview & Verification Status
- **Redis Connection Status**: **CONFIGURED (In-Memory Fallback Active)**
- **Active Adapter**: `in-memory-sliding-window` with `RedisEventBus` multi-worker support.
- **TLS & Authentication Support**: Supported via `rediss://` protocol and standard URI parsing.
- **Fail-Closed Strategy**: Verified via `RATE_LIMIT_FAIL_CLOSED_IN_PROD`.

---

## 2. Redis Staging Configuration Guide

To activate real distributed Redis on Staging/Production:

```bash
# Example Upstash / Redis Cloud URI:
REDIS_URL="rediss://default:your_secret_token@your-cluster.upstash.io:6379"
REDIS_CONNECT_TIMEOUT_SECONDS=2.0
RATE_LIMIT_FAIL_CLOSED_IN_PROD=true
```

### Operational Behavior:
1. **Multi-Worker Rate Limiting**: `SharedRateLimiter` automatically routes calls through `_check_redis`, using atomic pipelines (`zremrangebyscore`, `zcard`, `zadd`, `expire`) to eliminate concurrency races across Uvicorn workers.
2. **WebSocket Fan-Out**: `RedisEventBus` subscribes workers to `user_inbox_{user_id}` and `system_broadcast`, ensuring real-time messages reach users regardless of which server holds their WebSocket connection.
3. **Disconnection & Recovery**: If Redis drops, the connection pool catches `aioredis.ConnectionError`, logs a security warning, and gracefully resets the pool pointer. On sensitive authentication endpoints (`/auth/login`, `/auth/register`), requests fail closed (`503 Service Unavailable`) to prevent un-throttled credential attacks.
