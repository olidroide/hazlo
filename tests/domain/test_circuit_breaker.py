from __future__ import annotations

import time

from hazlo.domain.circuit_breaker import CircuitBreaker, CircuitState


class TestCircuitBreakerStateMachine:
    def test_initial_state_closed(self) -> None:
        cb = CircuitBreaker(name="test")
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute()

    def test_opens_after_threshold_failures(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert not cb.can_execute()

    def test_stays_closed_below_threshold(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED
        assert cb.can_execute()

    def test_resets_failure_count_on_success(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=3)
        cb.record_failure()
        cb.record_failure()
        cb.record_success()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    def test_transitions_to_half_open_after_timeout(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=1, reset_timeout_seconds=0.01)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN
        assert cb.can_execute()

    def test_half_open_success_closes_circuit(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=1, reset_timeout_seconds=0.01)
        cb.record_failure()
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_success()
        assert cb.state == CircuitState.CLOSED

    def test_half_open_failure_reopens_circuit(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=1, reset_timeout_seconds=0.01)
        cb.record_failure()
        time.sleep(0.02)
        assert cb.state == CircuitState.HALF_OPEN
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        assert not cb.can_execute()

    def test_manual_reset(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=1)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        cb.reset()
        assert cb.state == CircuitState.CLOSED

    def test_metrics(self) -> None:
        cb = CircuitBreaker(name="gemini-test")
        cb.record_success()
        cb.record_success()
        cb.record_failure()
        metrics = cb.metrics
        assert metrics["name"] == "gemini-test"
        assert metrics["state"] == "closed"
        assert metrics["total_successes"] == 2
        assert metrics["total_failures"] == 1

    def test_metrics_show_open_state(self) -> None:
        cb = CircuitBreaker(name="broken-provider", failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        metrics = cb.metrics
        assert metrics["state"] == "open"
        assert metrics["failure_count"] == 2


class TestCircuitBreakerEdgeCases:
    def test_zero_failure_threshold_opens_immediately(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=0)
        assert cb.state == CircuitState.CLOSED
        cb.record_failure()
        assert cb.state == CircuitState.OPEN

    def test_reset_clears_failure_count(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=2)
        cb.record_failure()
        cb.record_failure()
        cb.reset()
        cb.record_failure()
        assert cb.state == CircuitState.CLOSED

    def test_multiple_cycles(self) -> None:
        cb = CircuitBreaker(name="test", failure_threshold=1, reset_timeout_seconds=0.01)
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
        time.sleep(0.02)
        cb.record_success()
        assert cb.state == CircuitState.CLOSED
        cb.record_failure()
        assert cb.state == CircuitState.OPEN
