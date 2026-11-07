# PHASE 29 — REDIS AND REAL-TIME INFRASTRUCTURE

## 1. Overview & Dual-Mode Operations
Zynova's real-time communication and rate-limiting infrastructure supports a dual-mode pattern:
- **Distributed Mode (`REDIS_URL` configured)**: Utilizes Redis sorted sets for atomic sliding-window rate limiting across multiple backend workers, and Redis Pub/Sub channels for cross-container WebSocket event dispatch.
- **Single-Node Mode (Fallback / Local Dev)**: Falls back gracefully to in-memory sliding window counters and process-local asyncio event buses.

---

## 2. Redis Operational Architecture

### 2.1 Atomic Sliding-Window Rate Limiter
Implemented in `backend/app/core/rate_limit.py`:
```python
# Redis Pipeline:
pipe = r_client.pipeline()
pipe.zremrangebyscore(redis_key, 0, clear_before)
pipe.zcard(redis_key)
pipe.zadd(redis_key, {f"{now}_{time.perf_counter()}": now})
pipe.expire(redis_key, self.window_seconds + 5)
results = await pipe.execute()
```
- Eliminates race conditions across multiple Uvicorn worker processes.
- Memory leak free via automatic key TTL expiration (`expire`).

### 2.2 Redis Pub/Sub Event Bus (`RedisEventBus`)
Implemented in `backend/app/core/enhanced_ws_manager.py`:
- Channels partitioned per user inbox (`user_inbox_{user_id}`) and broadcast scopes (`system_broadcast`).
- Enables WebSocket clients connected to separate server instances to exchange real-time chat messages and calling signals seamlessly.

---

## 3. Failure Behavior & Outage Recovery
- **Redis Connection Drops**: The backend catches `aioredis.ConnectionError` and resets connection pools.
- **Fail-Closed vs Fail-Open**:
  - Sensitive operations (Login, Registration, Password Reset): If `RATE_LIMIT_FAIL_CLOSED_IN_PROD=True`, returns `503 Service Unavailable` to prevent un-throttled brute-force attacks.
  - General read operations: Gracefully falls back to local in-memory counters to maintain platform availability.
