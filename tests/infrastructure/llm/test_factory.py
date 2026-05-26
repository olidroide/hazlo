from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from hazlo.infrastructure.db.models import LLMProviderModel
from hazlo.infrastructure.llm.factory import build_pydantic_model


def _make_provider_model(
    provider_type: str = "groq",
    model: str = "llama-3.1-8b-instant",
) -> LLMProviderModel:
    return MagicMock(spec=LLMProviderModel, provider_type=provider_type, model=model)


@pytest.mark.asyncio
async def test_build_pydantic_model_returns_groq_model() -> None:
    provider = _make_provider_model()
    result = await build_pydantic_model(provider, "test-api-key")

    from pydantic_ai.models.groq import GroqModel

    assert isinstance(result, GroqModel)


@pytest.mark.asyncio
async def test_build_pydantic_model_returns_none_unknown() -> None:
    provider = _make_provider_model(provider_type="nonexistent")
    result = await build_pydantic_model(provider, "test-api-key")

    assert result is None
