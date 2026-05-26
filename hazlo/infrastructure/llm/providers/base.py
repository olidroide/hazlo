from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import ClassVar


@dataclass
class LLMResponse:
    content: str
    tokens_in: int = 0
    tokens_out: int = 0
    model: str = ""
    latency_ms: int = 0


@dataclass
class ModelInfo:
    id: str
    display_name: str
    is_free: bool
    description: str | None = None


class LLMProvider(ABC):
    """Protocol for LLM provider implementations."""

    provider_type: ClassVar[str] = ""

    @abstractmethod
    async def generate(
        self,
        system_prompt: str,
        user_content: str,
        temperature: float = 0.0,
        max_tokens: int = 500,
    ) -> LLMResponse:
        """Generate a response from the LLM.

        Returns LLMResponse with content and usage stats.
        Raises on API errors.
        """
        ...

    @abstractmethod
    async def test_connection(self) -> bool:
        """Test if the provider is reachable and authenticated.

        Returns True if connection successful, False otherwise.
        """
        ...

    @classmethod
    @abstractmethod
    async def list_models(cls, api_key: str) -> list[ModelInfo]:
        """List available models for this provider using the given API key.

        Returns list of ModelInfo, each with an is_free flag.
        """
        ...
