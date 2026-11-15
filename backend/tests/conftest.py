"""Pytest global fixtures for isolated Redis rate limiting, token revocation, and clean event loops."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import pytest

from app.core import rate_limit, token_revocation
from app.core.config import settings


class _FakePipeline:
    """In-memory async Redis pipeline supporting ZSET sliding-window operations."""

    def __init__(self, store: "_FakeAsyncRedis") -> None:
        self._store = store
        self._ops: List[Tuple[str, Tuple[Any, ...]]] = []

    def zremrangebyscore(self, key: str, min_score: float, max_score: float) -> "_FakePipeline":
        self._ops.append(("zremrangebyscore", (key, float(min_score), float(max_score))))
        return self

    def zcard(self, key: str) -> "_FakePipeline":
        self._ops.append(("zcard", (key,)))
        return self

    def zadd(self, key: str, mapping: Dict[str, float]) -> "_FakePipeline":
        self._ops.append(("zadd", (key, dict(mapping))))
        return self

    def expire(self, key: str, ttl: int) -> "_FakePipeline":
        self._ops.append(("expire", (key, int(ttl))))
        return self

    async def execute(self) -> List[Any]:
        results: List[Any] = []
        for op, args in self._ops:
            if op == "zremrangebyscore":
                key, min_s, max_s = args
                zset = self._store._zsets.setdefault(key, {})
                to_del = [m for m, sc in zset.items() if min_s <= sc <= max_s]
                for m in to_del:
                    del zset[m]
                results.append(len(to_del))
            elif op == "zcard":
                (key,) = args
                results.append(len(self._store._zsets.get(key, {})))
            elif op == "zadd":
                key, mapping = args
                zset = self._store._zsets.setdefault(key, {})
                added = 0
                for member, score in mapping.items():
                    if member not in zset:
                        added += 1
                    zset[member] = float(score)
                results.append(added)
            elif op == "expire":
                key, ttl = args
                self._store._expiries[key] = time.time() + ttl
                results.append(True)
        self._ops.clear()
        return results


class _FakeAsyncRedis:
    """Per-test isolated in-memory async Redis client (never touches production Redis)."""

    def __init__(self) -> None:
        self._kv: Dict[str, str] = {}
        self._expiries: Dict[str, float] = {}
        self._zsets: Dict[str, Dict[str, float]] = {}

    def _evict_if_expired(self, key: str) -> None:
        exp = self._expiries.get(key)
        if exp is not None and time.time() > exp:
            self._expiries.pop(key, None)
            self._kv.pop(key, None)
            self._zsets.pop(key, None)

    async def ping(self) -> bool:
        return True

    async def get(self, key: str) -> Optional[str]:
        self._evict_if_expired(key)
        return self._kv.get(key)

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        self._kv[key] = str(value)
        if ex is not None:
            self._expiries[key] = time.time() + int(ex)
        return True

    async def setex(self, key: str, ttl: int, value: str) -> bool:
        return await self.set(key, value, ex=ttl)

    async def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            if key in self._kv or key in self._zsets:
                removed += 1
            self._kv.pop(key, None)
            self._zsets.pop(key, None)
            self._expiries.pop(key, None)
        return removed

    def pipeline(self) -> _FakePipeline:
        return _FakePipeline(self)

    async def aclose(self) -> None:
        return None

    async def close(self) -> None:
        return None


_ALL_LIMITERS = [
    rate_limit.auth_rate_limiter,
    rate_limit.chat_rate_limiter,
    rate_limit.social_post_rate_limiter,
    rate_limit.comment_rate_limiter,
    rate_limit.report_rate_limiter,
    rate_limit.search_rate_limiter,
    rate_limit.video_upload_rate_limiter,
    rate_limit.video_comment_rate_limiter,
    rate_limit.food_order_rate_limiter,
    rate_limit.shopping_order_rate_limiter,
    rate_limit.payment_rate_limiter,
    rate_limit.balance_enquiry_rate_limiter,
]


@pytest.fixture(autouse=True)
def _isolate_rate_limiters_and_redis(monkeypatch: pytest.MonkeyPatch):
    """Isolate Redis state and reset all rate limiters between tests."""
    for limiter in _ALL_LIMITERS:
        limiter.clear()
    token_revocation._local_revoked_jtis.clear()

    fake_redis = _FakeAsyncRedis()

    async def _fake_get_redis_client() -> Optional[Any]:
        if not settings.REDIS_URL:
            return None
        return fake_redis

    monkeypatch.setattr(rate_limit, "get_redis_client", _fake_get_redis_client)
    monkeypatch.setattr(token_revocation, "get_redis_client", _fake_get_redis_client)
    try:
        from app.services import youtube_service
        if hasattr(youtube_service, "get_redis_client"):
            monkeypatch.setattr(youtube_service, "get_redis_client", _fake_get_redis_client)
    except ImportError:
        pass

    yield

    for limiter in _ALL_LIMITERS:
        limiter.clear()
    token_revocation._local_revoked_jtis.clear()
    rate_limit._redis_pool = None
    rate_limit._redis_pool_loop = None

