from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from hazlo.infrastructure.llm.providers.gemini import GeminiProvider
from hazlo.infrastructure.llm.providers.openrouter import OpenRouterProvider

GEMINI_RESPONSE = {
    "models": [
        {
            "name": "models/gemini-2.5-flash",
            "displayName": "Gemini 2.5 Flash",
            "description": "Fast and versatile model with a free tier.",
            "supportedGenerationMethods": ["generateContent", "countTokens"],
        },
        {
            "name": "models/gemini-2.5-pro",
            "displayName": "Gemini 2.5 Pro",
            "description": "Most capable model.",
            "supportedGenerationMethods": ["generateContent", "countTokens"],
        },
        {
            "name": "models/text-embedding-004",
            "displayName": "Text Embedding 004",
            "description": "Embeddings model.",
            "supportedGenerationMethods": ["embedContent"],
        },
    ],
}

OPENROUTER_RESPONSE = {
    "data": [
        {
            "id": "google/gemini-2.5-flash",
            "name": "Google: Gemini 2.5 Flash",
            "description": "Free Gemini model.",
            "pricing": {"prompt": "0", "completion": "0"},
        },
        {
            "id": "google/gemini-2.5-pro",
            "name": "Google: Gemini 2.5 Pro",
            "description": "Paid Gemini model.",
            "pricing": {"prompt": "1.25", "completion": "5"},
        },
        {
            "id": "openai/gpt-4o",
            "name": "OpenAI: GPT-4o",
            "description": "Paid OpenAI model via OpenRouter.",
            "pricing": {"prompt": "5", "completion": "15"},
        },
    ],
}


def _mock_client(json_response: dict) -> MagicMock:
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = json_response

    client = MagicMock()
    client.__aenter__.return_value = client
    client.get = AsyncMock(return_value=mock_response)
    return client


@pytest.mark.asyncio
async def test_gemini_list_models_filters_generate_content() -> None:
    client = _mock_client(GEMINI_RESPONSE)
    with patch("httpx.AsyncClient", return_value=client):
        models = await GeminiProvider.list_models("test-key")

    assert len(models) == 2
    ids = [m.id for m in models]
    assert "gemini-2.5-flash" in ids
    assert "gemini-2.5-pro" in ids
    assert "text-embedding-004" not in ids


@pytest.mark.asyncio
async def test_gemini_list_models_marks_flash_as_free() -> None:
    client = _mock_client(GEMINI_RESPONSE)
    with patch("httpx.AsyncClient", return_value=client):
        models = await GeminiProvider.list_models("test-key")

    flash = next(m for m in models if m.id == "gemini-2.5-flash")
    pro = next(m for m in models if m.id == "gemini-2.5-pro")
    assert flash.is_free is True
    assert pro.is_free is False


@pytest.mark.asyncio
async def test_gemini_list_models_sorts_free_first() -> None:
    client = _mock_client(GEMINI_RESPONSE)
    with patch("httpx.AsyncClient", return_value=client):
        models = await GeminiProvider.list_models("test-key")

    free_indices = [i for i, m in enumerate(models) if m.is_free]
    paid_indices = [i for i, m in enumerate(models) if not m.is_free]
    assert all(fi < pi for fi in free_indices for pi in paid_indices)


@pytest.mark.asyncio
async def test_gemini_list_models_strips_model_prefix() -> None:
    client = _mock_client(GEMINI_RESPONSE)
    with patch("httpx.AsyncClient", return_value=client):
        models = await GeminiProvider.list_models("test-key")

    assert not any(m.id.startswith("models/") for m in models)


@pytest.mark.asyncio
async def test_openrouter_list_models_detects_free_pricing() -> None:
    client = _mock_client(OPENROUTER_RESPONSE)
    with patch("httpx.AsyncClient", return_value=client):
        models = await OpenRouterProvider.list_models("test-key")

    assert len(models) == 3

    free_model = next(m for m in models if "flash" in m.id)
    paid_model = next(m for m in models if "pro" in m.id)
    gpt4o = next(m for m in models if "gpt-4o" in m.id)

    assert free_model.is_free is True
    assert paid_model.is_free is False
    assert gpt4o.is_free is False


@pytest.mark.asyncio
async def test_openrouter_list_models_sorts_free_first() -> None:
    client = _mock_client(OPENROUTER_RESPONSE)
    with patch("httpx.AsyncClient", return_value=client):
        models = await OpenRouterProvider.list_models("test-key")

    free_indices = [i for i, m in enumerate(models) if m.is_free]
    paid_indices = [i for i, m in enumerate(models) if not m.is_free]
    assert all(fi < pi for fi in free_indices for pi in paid_indices)


@pytest.mark.asyncio
async def test_openrouter_list_models_empty_returns_empty_list() -> None:
    client = _mock_client({"data": []})
    with patch("httpx.AsyncClient", return_value=client):
        models = await OpenRouterProvider.list_models("test-key")

    assert models == []


@pytest.mark.asyncio
async def test_gemini_list_models_empty_returns_empty_list() -> None:
    client = _mock_client({"models": []})
    with patch("httpx.AsyncClient", return_value=client):
        models = await GeminiProvider.list_models("test-key")

    assert models == []


@pytest.mark.asyncio
async def test_openrouter_list_models_zero_pricing_strings() -> None:
    client = _mock_client(
        {
            "data": [
                {
                    "id": "free/model",
                    "name": "Free Model",
                    "pricing": {"prompt": "0", "completion": "0"},
                },
            ],
        }
    )
    with patch("httpx.AsyncClient", return_value=client):
        models = await OpenRouterProvider.list_models("test-key")

    assert len(models) == 1
    assert models[0].is_free is True


@pytest.mark.asyncio
async def test_openrouter_list_models_missing_pricing() -> None:
    client = _mock_client(
        {
            "data": [
                {
                    "id": "some/model",
                    "name": "Some Model",
                    "pricing": {},
                },
            ],
        }
    )
    with patch("httpx.AsyncClient", return_value=client):
        models = await OpenRouterProvider.list_models("test-key")

    assert len(models) == 1
    assert models[0].is_free is False
