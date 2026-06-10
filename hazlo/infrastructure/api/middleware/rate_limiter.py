"""Rate limiter for admin actions."""

from __future__ import annotations

import time
import uuid

from fastapi import HTTPException


class RateLimiter:
    """In-memory rate limiter keyed by (user, resource)."""

    def __init__(self, max_calls: int = 5, window_seconds: int = 60) -> None:
        self._buckets: dict[tuple[str, str], list[float]] = {}
        self._max_calls = max_calls
        self._window = window_seconds

    def check(self, user: str, resource_id: uuid.UUID) -> None:
        now = time.monotonic()
        key = (user, str(resource_id))
        window = [t for t in self._buckets.get(key, []) if now - t < self._window]
        if len(window) >= self._max_calls:
            raise HTTPException(status_code=429, detail=f"Rate limit: {self._max_calls} calls per {self._window}s")
        self._buckets.setdefault(key, []).append(now)

    def reset(self) -> None:
        self._buckets.clear()


reparse_limiter = RateLimiter(max_calls=5, window_seconds=60)
