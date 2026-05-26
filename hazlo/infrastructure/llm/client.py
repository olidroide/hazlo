from __future__ import annotations

import logging
from dataclasses import dataclass

from hazlo.domain.circuit_breaker import CircuitBreaker
from hazlo.infrastructure.llm.providers.base import LLMProvider, LLMResponse

logger = logging.getLogger(__name__)


@dataclass
class LLMCallRecord:
    provider: str
    model: str
    action: str
    tokens_in: int
    tokens_out: int
    latency_ms: int
    error: str | None = None
    circuit_state: str | None = None


class LLMClient:
    """Provider router with automatic fallback and circuit breaker protection."""

    def __init__(
        self,
        providers: list[tuple[LLMProvider, str]],
        failure_threshold: int = 3,
        reset_timeout_seconds: float = 60.0,
        circuit_breakers: dict[str, CircuitBreaker] | None = None,
    ) -> None:
        self._providers = providers
        self._call_history: list[LLMCallRecord] = []
        self._circuit_breakers = circuit_breakers or {
            name: CircuitBreaker(
                name=name,
                failure_threshold=failure_threshold,
                reset_timeout_seconds=reset_timeout_seconds,
            )
            for _, name in providers
        }

    async def generate(
        self,
        system_prompt: str,
        user_content: str,
        action: str = "classify",
        temperature: float = 0.0,
        max_tokens: int = 500,
    ) -> LLMResponse:
        last_error: Exception | None = None
        skipped_open: list[str] = []

        for provider, name in self._providers:
            circuit = self._circuit_breakers.get(name)
            if circuit is not None and not circuit.can_execute():
                skipped_open.append(name)
                continue

            try:
                response = await provider.generate(
                    system_prompt=system_prompt,
                    user_content=user_content,
                    temperature=temperature,
                    max_tokens=max_tokens,
                )
                if circuit is not None:
                    circuit.record_success()
                self._call_history.append(
                    LLMCallRecord(
                        provider=name,
                        model=response.model,
                        action=action,
                        tokens_in=response.tokens_in,
                        tokens_out=response.tokens_out,
                        latency_ms=response.latency_ms,
                        circuit_state=circuit.state.value if circuit else None,
                    )
                )
                return response
            except Exception as exc:
                last_error = exc
                if circuit is not None:
                    circuit.record_failure()
                logger.warning(
                    "LLM provider %s failed (circuit=%s): %s",
                    name,
                    circuit.state.value if circuit else "none",
                    exc,
                )
                continue

        all_open = len(skipped_open) == len(self._providers)
        error_msg = f"All LLM providers failed. Last error: {last_error}"
        if skipped_open:
            error_msg = f"{error_msg}. Skipped (circuit open): {skipped_open}"
        if all_open:
            error_msg = f"All LLM providers have open circuits. Skipped: {skipped_open}"
        self._call_history.append(
            LLMCallRecord(
                provider="all",
                model="",
                action=action,
                tokens_in=0,
                tokens_out=0,
                latency_ms=0,
                error=error_msg,
            )
        )
        raise RuntimeError(error_msg)

    async def test_all_providers(self) -> dict[str, bool]:
        results: dict[str, bool] = {}
        for provider, name in self._providers:
            try:
                results[name] = await provider.test_connection()
            except Exception:
                logger.exception("Provider %s test_connection raised", name)
                results[name] = False
        return results

    @property
    def call_history(self) -> list[LLMCallRecord]:
        return list(self._call_history)

    @property
    def circuit_metrics(self) -> list[dict]:
        return [cb.metrics for cb in self._circuit_breakers.values()]

    def reset_all_circuits(self) -> None:
        for cb in self._circuit_breakers.values():
            cb.reset()
        logger.info("All circuit breakers reset")
