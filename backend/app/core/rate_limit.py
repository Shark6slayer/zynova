import time
import hashlib
import logging
from typing import Optional, Dict, Any
from collections import defaultdict
from fastapi import Request, HTTPException, status
from app.core.config import settings
from app.core.security_logger import log_security_event

logger = logging.getLogger("super_ai.rate_limit")

# Try importing redis for shared multi-worker rate limiting
try:
    import redis.asyncio as aioredis
    HAS_REDIS = True
except ImportError:
    aioredis = None
    HAS_REDIS = False

# Redis client singleton
_redis_pool: Optional[Any] = None

def get_masked_redis_url(url: Optional[str]) -> str:
    """Masks credentials in Redis connection URL for safe logging."""
    if not url:
        return "none"
    try:
        from urllib.parse import urlparse
        parsed = urlparse(url)
        netloc = parsed.hostname or "localhost"
        if parsed.port:
            netloc += f":{parsed.port}"
        return f"{parsed.scheme}://***@{netloc}{parsed.path}"
    except Exception:
        return "redis://***@masked"

async def get_redis_client() -> Optional[Any]:
    """Retrieves or initializes the async Redis client connection pool."""
    global _redis_pool
    if not HAS_REDIS or not settings.REDIS_URL:
        return None
    if _redis_pool is None:
        try:
            _redis_pool = aioredis.from_url(
                settings.REDIS_URL,
                socket_connect_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,
                socket_timeout=settings.REDIS_CONNECT_TIMEOUT_SECONDS,
                decode_responses=True
            )
            logger.info(f"Initialized shared Redis rate limiter connection: {get_masked_redis_url(settings.REDIS_URL)}")
        except Exception as e:
            logger.error(f"Failed to connect to Redis: {e}")
            return None
    return _redis_pool

async def close_redis_connection():
    """Closes Redis connection pool cleanly upon application shutdown."""
    global _redis_pool
    if _redis_pool is not None:
        try:
            await _redis_pool.close()
            logger.info("Closed Redis rate limiter connection pool.")
        except Exception as e:
            logger.warning(f"Error closing Redis pool: {e}")
        finally:
            _redis_pool = None

def get_client_ip(request: Request) -> str:
    """
    Safely resolves client IP.
    Does NOT trust arbitrary X-Forwarded-For headers unless connection originates from a configured trusted proxy.
    """
    direct_client = request.client.host if request.client else "127.0.0.1"
    
    if direct_client in settings.TRUSTED_PROXIES:
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Parse first untrusted IP in comma-separated list
            ips = [ip.strip() for ip in forwarded_for.split(",") if ip.strip()]
            for candidate in ips:
                if candidate not in settings.TRUSTED_PROXIES:
                    return candidate
    return direct_client

def hash_client_key(namespace: str, raw_key: str) -> str:
    """Hashes client identifiers to create stable, privacy-conscious rate-limit keys."""
    hashed = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:16]
    return f"rl:{namespace}:{hashed}"


class SharedRateLimiter:
    """
    Production-capable rate limiter supporting atomic Redis sliding-window counters,
    deterministic local in-memory fallback, and strict fail-closed policies in production.
    """
    def __init__(
        self,
        namespace: str,
        requests_limit: int = 10,
        window_seconds: int = 60,
        is_sensitive: bool = False
    ):
        self.namespace = namespace
        self.requests_limit = requests_limit
        self.window_seconds = window_seconds
        self.is_sensitive = is_sensitive
        # Memory fallback store (also preserves .requests for legacy test fixtures)
        self.requests = defaultdict(list)

    def _check_memory(self, key: str):
        """Synchronous in-memory sliding window check."""
        now = time.time()
        self.requests[key] = [t for t in self.requests[key] if now - t < self.window_seconds]
        if len(self.requests[key]) >= self.requests_limit:
            log_security_event(
                event_code="RATE_LIMIT_EXCEEDED",
                action=f"rate_limit:{self.namespace}",
                status="BLOCKED",
                details={"limit": self.requests_limit, "window": self.window_seconds, "backend": "memory"}
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for {self.namespace}. Please try again later."
            )
        self.requests[key].append(now)

    async def _check_redis(self, r_client: Any, key: str):
        """Atomic sliding window rate-limiting using Redis sorted sets (ZADD/ZREMRANGEBYSCORE)."""
        now = time.time()
        clear_before = now - self.window_seconds
        redis_key = f"{self.namespace}:{key}"

        pipe = r_client.pipeline()
        pipe.zremrangebyscore(redis_key, 0, clear_before)
        pipe.zcard(redis_key)
        pipe.zadd(redis_key, {f"{now}_{time.perf_counter()}": now})
        pipe.expire(redis_key, self.window_seconds + 5)
        results = await pipe.execute()

        current_count = results[1]
        if current_count >= self.requests_limit:
            log_security_event(
                event_code="RATE_LIMIT_EXCEEDED",
                action=f"rate_limit:{self.namespace}",
                status="BLOCKED",
                details={"limit": self.requests_limit, "window": self.window_seconds, "backend": "redis"}
            )
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"Rate limit exceeded for {self.namespace}. Please try again later."
            )

    async def check_async(self, raw_key: str):
        """Asynchronous rate limit check (preferred for FastAPI route handlers)."""
        r_client = await get_redis_client()
        key = hash_client_key(self.namespace, raw_key)

        if r_client is not None:
            try:
                await self._check_redis(r_client, key)
                return
            except HTTPException:
                raise
            except Exception as e:
                logger.warning(f"Redis rate check error ({self.namespace}): {e}")
                if settings.ENVIRONMENT.lower() == "production" and self.is_sensitive and settings.RATE_LIMIT_FAIL_CLOSED_IN_PROD:
                    log_security_event(
                        event_code="RATE_LIMIT_FAIL_CLOSED",
                        action=f"rate_limit:{self.namespace}",
                        status="ERROR",
                        details={"reason": "Redis unavailable on sensitive route in production"}
                    )
                    raise HTTPException(
                        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                        detail="Rate limiting service unavailable. Request rejected for security."
                    )

        # Fallback to in-memory store
        self._check_memory(key)

    def check(self, raw_key: str):
        """Synchronous check method preserved for backward-compatible call sites."""
        key = hash_client_key(self.namespace, raw_key)
        self._check_memory(key)

    def clear(self):
        """Clears memory counters for test isolation."""
        self.requests.clear()


# Preserved route-specific rate limiters with designated limits and sensitivity
auth_rate_limiter = SharedRateLimiter(namespace="auth", requests_limit=10, window_seconds=60, is_sensitive=True)
chat_rate_limiter = SharedRateLimiter(namespace="chat", requests_limit=60, window_seconds=60, is_sensitive=False)
social_post_rate_limiter = SharedRateLimiter(namespace="social_post", requests_limit=10, window_seconds=60, is_sensitive=False)
comment_rate_limiter = SharedRateLimiter(namespace="comment", requests_limit=30, window_seconds=60, is_sensitive=False)
report_rate_limiter = SharedRateLimiter(namespace="report", requests_limit=10, window_seconds=600, is_sensitive=True)
search_rate_limiter = SharedRateLimiter(namespace="search", requests_limit=60, window_seconds=60, is_sensitive=False)
video_upload_rate_limiter = SharedRateLimiter(namespace="video_upload", requests_limit=5, window_seconds=600, is_sensitive=True)
video_comment_rate_limiter = SharedRateLimiter(namespace="video_comment", requests_limit=30, window_seconds=60, is_sensitive=False)
food_order_rate_limiter = SharedRateLimiter(namespace="food_order", requests_limit=10, window_seconds=300, is_sensitive=True)
shopping_order_rate_limiter = SharedRateLimiter(namespace="shopping_order", requests_limit=10, window_seconds=300, is_sensitive=True)
payment_rate_limiter = SharedRateLimiter(namespace="payment", requests_limit=15, window_seconds=60, is_sensitive=True)
balance_enquiry_rate_limiter = SharedRateLimiter(namespace="balance_enquiry", requests_limit=10, window_seconds=60, is_sensitive=True)


# Route dependency wrappers
async def check_auth_rate_limit(request: Request):
    client_ip = get_client_ip(request)
    await auth_rate_limiter.check_async(client_ip)

def check_chat_user_rate_limit(user_id: str):
    chat_rate_limiter.check(user_id)

def check_social_post_rate_limit(user_id: str):
    social_post_rate_limiter.check(user_id)

def check_comment_rate_limit(user_id: str):
    comment_rate_limiter.check(user_id)

def check_report_rate_limit(user_id: str):
    report_rate_limiter.check(user_id)

async def check_search_rate_limit(request: Request):
    client_ip = get_client_ip(request)
    await search_rate_limiter.check_async(client_ip)

def check_video_upload_rate_limit(user_id: str):
    video_upload_rate_limiter.check(user_id)

def check_video_comment_rate_limit(user_id: str):
    video_comment_rate_limiter.check(user_id)

def check_food_order_rate_limit(user_id: str):
    food_order_rate_limiter.check(user_id)

def check_shopping_order_rate_limit(user_id: str):
    shopping_order_rate_limiter.check(user_id)

def check_payment_rate_limit(user_id: str):
    payment_rate_limiter.check(user_id)

def check_balance_enquiry_rate_limit(user_id: str):
    balance_enquiry_rate_limiter.check(user_id)


async def get_rate_limiter_health() -> Dict[str, Any]:
    """Returns operational health status of the rate limiter backend."""
    r_client = await get_redis_client()
    if r_client is not None:
        try:
            await r_client.ping()
            return {
                "status": "healthy",
                "backend": "redis",
                "connected": True,
                "url": get_masked_redis_url(settings.REDIS_URL)
            }
        except Exception as e:
            return {
                "status": "degraded",
                "backend": "redis",
                "connected": False,
                "error": str(e)
            }
    return {
        "status": "operational",
        "backend": "in-memory-sliding-window",
        "connected": True,
        "note": "Development/testing fallback active. Configure REDIS_URL for multi-worker production cluster."
    }
