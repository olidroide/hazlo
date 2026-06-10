"""Tests for rate limiter."""

from __future__ import annotations

import uuid

import pytest
from fastapi import HTTPException

from hazlo.infrastructure.api.middleware.rate_limiter import RateLimiter


def test_rate_limiter_allows_within_limit() -> None:
    limiter = RateLimiter(max_calls=3, window_seconds=60)
    user = "admin"
    resource = uuid.uuid4()

    for _ in range(3):
        limiter.check(user, resource)


def test_rate_limiter_blocks_over_limit() -> None:
    limiter = RateLimiter(max_calls=2, window_seconds=60)
    user = "admin"
    resource = uuid.uuid4()

    limiter.check(user, resource)
    limiter.check(user, resource)

    with pytest.raises(HTTPException) as exc_info:
        limiter.check(user, resource)

    assert exc_info.value.status_code == 429


def test_rate_limiter_different_resources_independent() -> None:
    limiter = RateLimiter(max_calls=1, window_seconds=60)
    user = "admin"
    r1 = uuid.uuid4()
    r2 = uuid.uuid4()

    limiter.check(user, r1)

    with pytest.raises(HTTPException) as exc_info:
        limiter.check(user, r1)
    assert exc_info.value.status_code == 429

    limiter.check(user, r2)


def test_rate_limiter_reset() -> None:
    limiter = RateLimiter(max_calls=1, window_seconds=60)
    user = "admin"
    resource = uuid.uuid4()

    limiter.check(user, resource)
    limiter.reset()
    limiter.check(user, resource)
