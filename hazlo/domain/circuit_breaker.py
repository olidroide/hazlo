from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class CircuitBreaker:
    """Per-provider circuit breaker for LLM fault tolerance.

    State machine:
    CLOSED ──(consecutive failures >= failure_threshold)──▶ OPEN
    OPEN   ──(timeout_ms elapsed)───────────────────────▶ HALF_OPEN
    HALF_OPEN ──(success)────────────────────────────────▶ CLOSED
    HALF_OPEN ──(failure)────────────────────────────────▶ OPEN
    """

    name: str
    failure_threshold: int = 3
    reset_timeout_seconds: float = 60.0
    _state: CircuitState = CircuitState.CLOSED
    _failure_count: int = 0
    _last_failure_time: float = 0.0
    _opened_at: float = 0.0
    _success_count: int = 0
    _total_failures: int = 0
    _total_successes: int = 0

    @property
    def state(self) -> CircuitState:
        if self._state == CircuitState.OPEN and time.monotonic() - self._opened_at >= self.reset_timeout_seconds:
            self._state = CircuitState.HALF_OPEN
        return self._state

    def can_execute(self) -> bool:
        return self.state != CircuitState.OPEN

    def record_success(self) -> None:
        self._total_successes += 1
        if self.state == CircuitState.HALF_OPEN:
            self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count += 1

    def record_failure(self) -> None:
        self._total_failures += 1
        self._failure_count += 1
        self._last_failure_time = time.monotonic()
        if self._state == CircuitState.HALF_OPEN or self._failure_count >= self.failure_threshold:
            self._state = CircuitState.OPEN
            self._opened_at = time.monotonic()

    def reset(self) -> None:
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0

    @property
    def metrics(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "total_failures": self._total_failures,
            "total_successes": self._total_successes,
        }
