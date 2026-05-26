from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from hazlo.infrastructure.api import deps
from hazlo.infrastructure.api.routes.admin_llm_providers import ModelInfo
from hazlo.infrastructure.db.models import LLMProviderModel
from hazlo.infrastructure.db.repositories import LLMProviderRepository
from hazlo.main import app


def _make_provider_model(**overrides: object) -> LLMProviderModel:
    now = datetime.now(UTC)
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "name": "Test Provider",
        "provider_type": "gemini",
        "model": "gemini-2.0-flash",
        "api_key_encrypted": "gAAAAABfake==",
        "is_active": False,
        "priority": 0,
        "max_calls_per_run": 100,
        "cost_per_1k_tokens_micros": 1500,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return LLMProviderModel(**defaults)  # type: ignore[arg-type]


def _set_provider_repo_override(repo: LLMProviderRepository) -> None:
    app.dependency_overrides[deps.get_llm_provider_repo] = lambda: repo


def _client() -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


@pytest.mark.asyncio
async def test_list_providers_returns_200() -> None:
    mock_repo = MagicMock(spec=LLMProviderRepository)
    mock_repo.list_all = AsyncMock(return_value=[])

    _set_provider_repo_override(mock_repo)
    try:
        async with _client() as client:
            response = await client.get("/admin/llm-providers/")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_list_providers_shows_provider() -> None:
    provider = _make_provider_model(
        name="Gemini Test",
        provider_type="gemini",
        model="gemini-pro",
    )
    mock_repo = MagicMock(spec=LLMProviderRepository)
    mock_repo.list_all = AsyncMock(return_value=[provider])

    _set_provider_repo_override(mock_repo)
    try:
        async with _client() as client:
            response = await client.get("/admin/llm-providers/")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Gemini Test" in response.text
    assert "gemini-pro" in response.text


@pytest.mark.asyncio
async def test_list_providers_shows_active_status() -> None:
    provider = _make_provider_model(is_active=True)
    mock_repo = MagicMock(spec=LLMProviderRepository)
    mock_repo.list_all = AsyncMock(return_value=[provider])

    _set_provider_repo_override(mock_repo)
    try:
        async with _client() as client:
            response = await client.get("/admin/llm-providers/")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Active" in response.text


@pytest.mark.asyncio
async def test_list_providers_shows_cost_per_1k() -> None:
    provider = _make_provider_model(cost_per_1k_tokens_micros=2500000)
    mock_repo = MagicMock(spec=LLMProviderRepository)
    mock_repo.list_all = AsyncMock(return_value=[provider])

    _set_provider_repo_override(mock_repo)
    try:
        async with _client() as client:
            response = await client.get("/admin/llm-providers/")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "2.5000" in response.text


@pytest.mark.asyncio
async def test_list_providers_cost_micros_none_shows_dash() -> None:
    provider = _make_provider_model(cost_per_1k_tokens_micros=0)
    mock_repo = MagicMock(spec=LLMProviderRepository)
    mock_repo.list_all = AsyncMock(return_value=[provider])

    _set_provider_repo_override(mock_repo)
    try:
        async with _client() as client:
            response = await client.get("/admin/llm-providers/")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "-" in response.text


@pytest.mark.asyncio
async def test_new_provider_form_returns_200() -> None:
    async with _client() as client:
        response = await client.get("/admin/llm-providers/_new")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_new_provider_form_has_provider_dropdown() -> None:
    async with _client() as client:
        response = await client.get("/admin/llm-providers/_new")
    assert response.status_code == 200
    assert "provider_type" in response.text
    assert "Google Gemini" in response.text
    assert "OpenRouter" in response.text
    assert "api_key" in response.text
    assert "Fetch Models" in response.text


@pytest.mark.asyncio
async def test_activate_provider_returns_row_html() -> None:
    provider = _make_provider_model(is_active=False)
    activated = _make_provider_model(id=provider.id, is_active=True)
    mock_repo = MagicMock(spec=LLMProviderRepository)
    mock_repo.set_active = AsyncMock(return_value=activated)

    _set_provider_repo_override(mock_repo)
    try:
        async with _client() as client:
            response = await client.post(f"/admin/llm-providers/{provider.id}/activate")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "Active" in response.text
    assert "Activate" not in response.text


@pytest.mark.asyncio
async def test_activate_provider_not_found() -> None:
    provider_id = uuid.uuid4()
    mock_repo = MagicMock(spec=LLMProviderRepository)
    mock_repo.set_active = AsyncMock(return_value=None)

    _set_provider_repo_override(mock_repo)
    try:
        async with _client() as client:
            response = await client.post(f"/admin/llm-providers/{provider_id}/activate")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_delete_provider_returns_empty_200() -> None:
    provider_id = uuid.uuid4()
    mock_repo = MagicMock(spec=LLMProviderRepository)
    mock_repo.delete = AsyncMock(return_value=True)

    _set_provider_repo_override(mock_repo)
    try:
        async with _client() as client:
            response = await client.delete(f"/admin/llm-providers/{provider_id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.text == ""


@pytest.mark.asyncio
async def test_delete_provider_not_found() -> None:
    provider_id = uuid.uuid4()
    mock_repo = MagicMock(spec=LLMProviderRepository)
    mock_repo.delete = AsyncMock(return_value=False)

    _set_provider_repo_override(mock_repo)
    try:
        async with _client() as client:
            response = await client.delete(f"/admin/llm-providers/{provider_id}")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


@pytest.mark.asyncio
async def test_test_provider_not_found_returns_404() -> None:
    provider_id = uuid.uuid4()
    mock_repo = MagicMock(spec=LLMProviderRepository)
    mock_repo.get = AsyncMock(return_value=None)

    _set_provider_repo_override(mock_repo)
    try:
        async with _client() as client:
            response = await client.post(f"/admin/llm-providers/{provider_id}/test")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404


# ── /models endpoint tests ──────────────────────────────────────────────


def _sample_models() -> list[ModelInfo]:
    return [
        ModelInfo(id="gemini-2.5-flash", display_name="Gemini 2.5 Flash", is_free=True, description="Fast model"),
        ModelInfo(id="gemini-2.5-pro", display_name="Gemini 2.5 Pro", is_free=False, description="Powerful model"),
    ]


@pytest.mark.asyncio
async def test_list_models_endpoint_gemini_returns_200() -> None:
    async def _list_models(provider_type: str, api_key: str) -> list[ModelInfo]:
        return _sample_models()

    with patch("hazlo.infrastructure.api.routes.admin_llm_providers._list_models", _list_models):
        async with _client() as client:
            response = await client.post(
                "/admin/llm-providers/models",
                data={
                    "provider_type": "gemini",
                    "api_key": "test-key",
                },
            )

    assert response.status_code == 200
    assert "gemini-2.5-flash" in response.text
    assert "gemini-2.5-pro" in response.text
    assert "Free" in response.text
    assert "Paid" in response.text


@pytest.mark.asyncio
async def test_list_models_endpoint_shows_model_count() -> None:
    async def _list_models(provider_type: str, api_key: str) -> list[ModelInfo]:
        return _sample_models()

    with patch("hazlo.infrastructure.api.routes.admin_llm_providers._list_models", _list_models):
        async with _client() as client:
            response = await client.post(
                "/admin/llm-providers/models",
                data={
                    "provider_type": "gemini",
                    "api_key": "test-key",
                },
            )

    assert "2 model(s) available" in response.text


@pytest.mark.asyncio
async def test_list_models_endpoint_unknown_provider_returns_400() -> None:
    async with _client() as client:
        response = await client.post(
            "/admin/llm-providers/models",
            data={
                "provider_type": "nonexistent",
                "api_key": "test-key",
            },
        )

    assert response.status_code == 400


@pytest.mark.asyncio
async def test_list_models_endpoint_api_error_shows_error_in_html() -> None:
    async def _list_models_error(provider_type: str, api_key: str) -> list[ModelInfo]:
        raise RuntimeError("Invalid API key")

    with patch("hazlo.infrastructure.api.routes.admin_llm_providers._list_models", _list_models_error):
        async with _client() as client:
            response = await client.post(
                "/admin/llm-providers/models",
                data={
                    "provider_type": "gemini",
                    "api_key": "bad-key",
                },
            )

    assert response.status_code == 200
    assert "Failed to fetch models" in response.text


@pytest.mark.asyncio
async def test_list_models_endpoint_no_models_shows_warning() -> None:
    async def _list_models_empty(provider_type: str, api_key: str) -> list[ModelInfo]:
        return []

    with patch("hazlo.infrastructure.api.routes.admin_llm_providers._list_models", _list_models_empty):
        async with _client() as client:
            response = await client.post(
                "/admin/llm-providers/models",
                data={
                    "provider_type": "gemini",
                    "api_key": "test-key",
                },
            )

    assert response.status_code == 200
    assert "No models found" in response.text


@pytest.mark.asyncio
async def test_list_models_endpoint_has_radio_inputs() -> None:
    async def _list_models(provider_type: str, api_key: str) -> list[ModelInfo]:
        return _sample_models()

    with patch("hazlo.infrastructure.api.routes.admin_llm_providers._list_models", _list_models):
        async with _client() as client:
            response = await client.post(
                "/admin/llm-providers/models",
                data={
                    "provider_type": "gemini",
                    "api_key": "test-key",
                },
            )

    assert 'type="radio"' in response.text
    assert 'name="model"' in response.text
