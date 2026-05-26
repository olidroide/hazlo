from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import pytest

from hazlo.domain.source import SourceType
from hazlo.infrastructure.db.models import SourceModel, model_to_source


def test_sourcetype_has_expected_values() -> None:
    assert SourceType.RSS.value == "rss"
    assert SourceType.WEB.value == "web"
    assert SourceType.EMAIL.value == "email"


def test_sourcetype_from_valid_string() -> None:
    assert SourceType("rss") == SourceType.RSS
    assert SourceType("web") == SourceType.WEB
    assert SourceType("email") == SourceType.EMAIL


def test_sourcetype_from_invalid_string_raises_valueerror() -> None:
    with pytest.raises(ValueError, match="'csv' is not a valid SourceType"):
        SourceType("csv")


def test_sourcetype_from_invalid_string_raises_valueerror_atom() -> None:
    with pytest.raises(ValueError, match="'atom' is not a valid SourceType"):
        SourceType("atom")


def test_sourcetype_from_empty_string_raises_valueerror() -> None:
    with pytest.raises(ValueError):
        SourceType("")


def test_model_to_source_valid_type() -> None:
    model = MagicMock(spec=SourceModel)
    model.id = uuid.uuid4()
    model.name = "Test"
    model.source_type = "rss"
    model.url = "https://example.com"
    model.config = {}
    model.is_active = True
    model.fetch_interval_minutes = 60
    model.last_run_at = None
    model.last_run_status = None

    result = model_to_source(model)
    assert result.source_type == SourceType.RSS


def test_model_to_source_invalid_type_raises() -> None:
    model = MagicMock(spec=SourceModel)
    model.source_type = "invalid"

    with pytest.raises(ValueError, match="'invalid' is not a valid SourceType"):
        model_to_source(model)
