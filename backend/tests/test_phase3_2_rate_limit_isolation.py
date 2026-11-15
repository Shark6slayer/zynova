"""Phase 3.2 tests for Redis rate-limiter isolation and concurrent authentication rate limiting."""

from __future__ import annotations

import asyncio

import pytest
from fastapi import HTTPException

from app.core.rate_limit import auth_rate_limiter


@pytest.mark.asyncio
async def test_concurrent_auth_requests_enforce_rate_limit_in_isolated_test() -> None:
    """Verify 10 concurrent auth checks pass and the 11th+ are rejected with HTTP 429."""
    async def _attempt() -> int:
        try:
            await auth_rate_limiter.check_async("198.51.100.42")
            return 200
        except HTTPException as exc:
            return exc.status_code

    results = await asyncio.gather(*(_attempt() for _ in range(13)))
    assert results.count(200) == 10
    assert results.count(429) == 3

