from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(frozen=True)
class LLMProviderConfig:
    provider_type: str  # gemini, openrouter, openai, anthropic
    model: str
    api_key: str
    max_calls_per_run: int = 100
    cost_per_1k_tokens: float = 0.0


@dataclass
class LLMProvider:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    name: str = ""
    config: LLMProviderConfig | None = None
    is_active: bool = False
    priority: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def activate(self) -> None:
        object.__setattr__(self, "is_active", True)

    def deactivate(self) -> None:
        object.__setattr__(self, "is_active", False)
