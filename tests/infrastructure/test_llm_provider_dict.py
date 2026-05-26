from __future__ import annotations

import uuid
from datetime import UTC, datetime

from hazlo.infrastructure.api.routes.admin_llm_providers import _provider_dict
from hazlo.infrastructure.db.models import LLMProviderModel


def _make_provider_model(**overrides: object) -> LLMProviderModel:
    now = datetime.now(UTC)
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "name": "Test Provider",
        "provider_type": "gemini",
        "model": "gemini-2.0-flash",
        "api_key_encrypted": "encrypted-key-data",
        "is_active": False,
        "priority": 0,
        "max_calls_per_run": 100,
        "cost_per_1k_tokens_micros": 0,
        "created_at": now,
        "updated_at": now,
    }
    defaults.update(overrides)
    return LLMProviderModel(**defaults)  # type: ignore[arg-type]


def test_provider_dict_return_keys() -> None:
    model = _make_provider_model()
    result = _provider_dict(model)

    assert "id" in result
    assert "name" in result
    assert "provider_type" in result
    assert "model" in result
    assert "is_active" in result
    assert "priority" in result
    assert "max_calls_per_run" in result
    assert "cost_per_1k_tokens_micros" in result
    assert "created_at" in result
    assert "updated_at" in result


def test_provider_dict_maps_fields() -> None:
    model = _make_provider_model(
        name="Google Gemini",
        provider_type="gemini",
        model="gemini-pro",
        is_active=True,
        priority=5,
        cost_per_1k_tokens_micros=1250,
    )
    result = _provider_dict(model)

    assert result["name"] == "Google Gemini"
    assert result["provider_type"] == "gemini"
    assert result["model"] == "gemini-pro"
    assert result["is_active"] is True
    assert result["priority"] == 5
    assert result["cost_per_1k_tokens_micros"] == 1250


def test_provider_dict_id_is_uuid() -> None:
    provider_id = uuid.uuid4()
    model = _make_provider_model(id=provider_id)
    result = _provider_dict(model)

    assert result["id"] == provider_id


def test_provider_dict_cost_per_1k_tokens_micros_default_zero() -> None:
    model = _make_provider_model()
    result = _provider_dict(model)

    assert result["cost_per_1k_tokens_micros"] == 0


def test_provider_dict_created_at_is_datetime() -> None:
    now = datetime.now(UTC)
    model = _make_provider_model(created_at=now)
    result = _provider_dict(model)

    assert result["created_at"] == now
