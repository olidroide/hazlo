from __future__ import annotations

import pytest

from hazlo.domain.circuit_breaker import CircuitBreaker, CircuitState
from hazlo.infrastructure.llm.client import LLMClient
from hazlo.infrastructure.llm.providers.base import LLMProvider, LLMResponse


class CountingProvider(LLMProvider):
    def __init__(self, name: str = "test", fail_count: int = 0) -> None:
        self.name = name
        self.fail_count = fail_count
        self.call_count = 0
        self._failures_left = fail_count

    async def generate(
        self,
        system_prompt: str = "",
        user_content: str = "",
        temperature: float = 0.0,
        max_tokens: int = 500,
    ) -> LLMResponse:
        self.call_count += 1
        if self._failures_left > 0:
            self._failures_left -= 1
            msg = "Provider failure"
            raise ConnectionError(msg)
        return LLMResponse(
            content='{"is_children_activity": true}',
            tokens_in=10,
            tokens_out=5,
            model=self.name,
            latency_ms=5,
        )

    async def test_connection(self) -> bool:
        return self._failures_left == 0

    @classmethod
    async def list_models(cls, api_key: str) -> list:
        return []


class TestCircuitBreakerIntegration:
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self) -> None:
        primary = CountingProvider(name="primary", fail_count=5)
        secondary = CountingProvider(name="secondary", fail_count=5)

        cb = CircuitBreaker(name="primary", failure_threshold=2)
        client = LLMClient(
            [(primary, "primary"), (secondary, "secondary")],
            circuit_breakers={
                "primary": cb,
                "secondary": CircuitBreaker(name="secondary", failure_threshold=2),
            },
        )

        for _ in range(2):
            with pytest.raises(RuntimeError):
                await client.generate(system_prompt="hi", user_content="hi")

        assert cb.state == CircuitState.OPEN
        assert not cb.can_execute()
        assert primary.call_count >= 2

    @pytest.mark.asyncio
    async def test_circuit_breaker_records_success(self) -> None:
        provider = CountingProvider(name="primary")

        cb = CircuitBreaker(name="primary", failure_threshold=3)
        client = LLMClient(
            [(provider, "primary")],
            circuit_breakers={"primary": cb},
        )

        await client.generate(system_prompt="hi", user_content="hi")

        assert cb.state == CircuitState.CLOSED
        assert cb.metrics["total_successes"] == 1

    @pytest.mark.asyncio
    async def test_skips_open_circuit_providers(self) -> None:
        primary = CountingProvider(name="primary", fail_count=5)

        cb = CircuitBreaker(name="primary", failure_threshold=1)
        client = LLMClient(
            [(primary, "primary")],
            circuit_breakers={
                "primary": cb,
            },
        )

        with pytest.raises(RuntimeError):
            await client.generate(system_prompt="hi", user_content="hi")

        assert cb.state == CircuitState.OPEN

        with pytest.raises(RuntimeError, match="open circuits"):
            await client.generate(system_prompt="hi", user_content="hi")

    @pytest.mark.asyncio
    async def test_all_circuits_open_raises(self) -> None:
        primary = CountingProvider(name="primary", fail_count=5)
        secondary = CountingProvider(name="secondary", fail_count=5)

        cb1 = CircuitBreaker(name="primary", failure_threshold=1)
        cb2 = CircuitBreaker(name="secondary", failure_threshold=1)
        client = LLMClient(
            [(primary, "primary"), (secondary, "secondary")],
            circuit_breakers={"primary": cb1, "secondary": cb2},
        )

        with pytest.raises(RuntimeError):
            await client.generate(system_prompt="hi", user_content="hi")

        assert cb1.state == CircuitState.OPEN
        assert cb2.state == CircuitState.OPEN

        with pytest.raises(RuntimeError, match="open circuits"):
            await client.generate(system_prompt="hi", user_content="hi")

    @pytest.mark.asyncio
    async def test_circuit_breaker_metrics_in_call_history(self) -> None:
        provider = CountingProvider(name="primary")
        client = LLMClient(
            [(provider, "primary")],
            circuit_breakers={"primary": CircuitBreaker(name="primary", failure_threshold=3)},
        )

        await client.generate(system_prompt="hi", user_content="hi")

        records = client.call_history
        assert len(records) == 1
        assert records[0].circuit_state == "closed"

    @pytest.mark.asyncio
    async def test_circuit_metrics_property(self) -> None:
        provider = CountingProvider(name="primary", fail_count=1)
        cb = CircuitBreaker(name="primary", failure_threshold=5)
        client = LLMClient(
            [(provider, "primary")],
            circuit_breakers={"primary": cb},
        )

        with pytest.raises(RuntimeError):
            await client.generate(system_prompt="hi", user_content="hi")

        metrics = client.circuit_metrics
        assert len(metrics) == 1
        assert metrics[0]["name"] == "primary"
        assert metrics[0]["total_failures"] == 1

    @pytest.mark.asyncio
    async def test_reset_all_circuits(self) -> None:
        provider = CountingProvider(name="primary", fail_count=5)
        cb = CircuitBreaker(name="primary", failure_threshold=1)
        client = LLMClient(
            [(provider, "primary")],
            circuit_breakers={"primary": cb},
        )

        with pytest.raises(RuntimeError):
            await client.generate(system_prompt="hi", user_content="hi")

        assert cb.state == CircuitState.OPEN

        client.reset_all_circuits()
        assert cb.state == CircuitState.CLOSED

    @pytest.mark.asyncio
    async def test_default_circuit_breakers_created(self) -> None:
        provider = CountingProvider(name="auto-cb")
        client = LLMClient([(provider, "auto-cb")], failure_threshold=2)

        assert "auto-cb" in client._circuit_breakers
        assert client._circuit_breakers["auto-cb"].failure_threshold == 2
