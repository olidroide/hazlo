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
async def test_toggle_provider_active_returns_row_html() -> None:
    provider = _make_provider_model(is_active=False)
    toggled = _make_provider_model(id=provider.id, is_active=True)
    mock_repo = MagicMock(spec=LLMProviderRepository)
    mock_repo.toggle_active = AsyncMock(return_value=toggled)

    _set_provider_repo_override(mock_repo)
    try:
        async with _client() as client:
            response = await client.post(f"/admin/llm-providers/{provider.id}/toggle-active")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert "checked" in response.text


@pytest.mark.asyncio
async def test_toggle_provider_active_not_found() -> None:
    provider_id = uuid.uuid4()
    mock_repo = MagicMock(spec=LLMProviderRepository)
    mock_repo.toggle_active = AsyncMock(return_value=None)

    _set_provider_repo_override(mock_repo)
    try:
        async with _client() as client:
            response = await client.post(f"/admin/llm-providers/{provider_id}/toggle-active")
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


# ── Groq provider tests ────────────────────────────────────────────────


@patch("httpx.AsyncClient")
@pytest.mark.asyncio
async def test_list_groq_models_returns_known_models(mock_async_client: MagicMock) -> None:
    from hazlo.infrastructure.api.routes.admin_llm_providers import _list_groq_models

    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()
    mock_response.json = MagicMock(
        return_value={
            "data": [
                {"id": "llama-3.1-8b-instant", "owned_by": "groq"},
                {"id": "gemma2-9b-it", "owned_by": "groq"},
                {"id": "llama-3.3-70b-versatile", "owned_by": "groq"},
            ]
        }
    )
    mock_client_instance = AsyncMock()
    mock_client_instance.get = AsyncMock(return_value=mock_response)
    mock_client_instance.__aenter__ = AsyncMock(return_value=mock_client_instance)
    mock_client_instance.__aexit__ = AsyncMock(return_value=False)
    mock_async_client.return_value = mock_client_instance

    models = await _list_groq_models("test-api-key")

    assert len(models) >= 3
    model_ids = [m.id for m in models]
    assert "llama-3.1-8b-instant" in model_ids
    assert "gemma2-9b-it" in model_ids
    assert all(m.is_free for m in models)


@pytest.mark.asyncio
async def test_list_models_endpoint_groq_returns_200() -> None:
    async def _list_models(provider_type: str, api_key: str) -> list:
        from hazlo.infrastructure.api.routes.admin_llm_providers import ModelInfo

        return [
            ModelInfo(id="llama-3.1-8b-instant", display_name="Llama 3.1 8B Instant", is_free=True),
            ModelInfo(id="gemma2-9b-it", display_name="Gemma 2 9B IT", is_free=True),
        ]

    with patch("hazlo.infrastructure.api.routes.admin_llm_providers._list_models", _list_models):
        async with _client() as client:
            response = await client.post(
                "/admin/llm-providers/models",
                data={
                    "provider_type": "groq",
                    "api_key": "test-key",
                },
            )

    assert response.status_code == 200
    assert "llama-3.1-8b-instant" in response.text
    assert "gemma2-9b-it" in response.text


@pytest.mark.asyncio
async def test_new_provider_form_has_groq_in_dropdown() -> None:
    async with _client() as client:
        response = await client.get("/admin/llm-providers/_new")
    assert response.status_code == 200
    assert "Groq" in response.text
    assert 'value="groq"' in response.text


@pytest.mark.asyncio
async def test_toggle_provider_updates_correct_row_with_htmx() -> None:
    """TDD Test: Verify toggle updates the CORRECT provider row, not the first row.

    This test verifies that:
    1. Checkbox has correct hx-target (provider-row-ID)
    2. Checkbox is disabled during request (hx-disabled-elt)
    3. Loading indicator is present (hx-indicator)
    4. Response contains the correct row ID in the HTML
    """
    provider2 = _make_provider_model(id=uuid.uuid4(), name="Provider 2", is_active=False)

    toggled_provider2 = _make_provider_model(id=provider2.id, name="Provider 2", is_active=True)

    mock_repo = MagicMock(spec=LLMProviderRepository)
    mock_repo.toggle_active = AsyncMock(return_value=toggled_provider2)

    _set_provider_repo_override(mock_repo)
    try:
        async with _client() as client:
            response = await client.post(f"/admin/llm-providers/{provider2.id}/toggle-active")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200

    # ✅ Verify response is the CORRECT row with provider2's ID
    assert f'id="provider-row-{provider2.id}"' in response.text
    assert "Provider 2" in response.text
    assert "checked" in response.text  # is_active=True

    # ✅ Verify HTMX attributes are present in the checkbox
    assert f'hx-target="#provider-row-{provider2.id}"' in response.text
    assert 'hx-disabled-elt="this"' in response.text
    assert f'hx-indicator="#loading-{provider2.id}"' in response.text

    # ✅ Verify loading indicator div exists
    assert f'id="loading-{provider2.id}"' in response.text
    assert "animate-spin" in response.text

    # ✅ Verify response headers guide HTMX (if retargeting is needed)
    assert response.headers.get("HX-Retarget") == f"#provider-row-{provider2.id}"
    assert response.headers.get("HX-Reswap") == "outerHTML"
