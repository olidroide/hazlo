from __future__ import annotations

import pytest
from pydantic import ValidationError

from hazlo.domain.llm_output import ClassificationOutput, LocationEnrichmentOutput


class TestClassificationOutput:
    def test_valid_classification(self) -> None:
        output = ClassificationOutput(
            is_children_activity=True,
            is_toddler_friendly=False,
            confidence=0.85,
        )

        assert output.is_children_activity is True
        assert output.is_toddler_friendly is False
        assert output.confidence == 0.85

    def test_confidence_boundary_low(self) -> None:
        output = ClassificationOutput(
            is_children_activity=False,
            is_toddler_friendly=False,
            confidence=0.0,
        )

        assert output.confidence == 0.0

    def test_confidence_boundary_high(self) -> None:
        output = ClassificationOutput(
            is_children_activity=True,
            is_toddler_friendly=True,
            confidence=1.0,
        )

        assert output.confidence == 1.0

    def test_confidence_out_of_range_high(self) -> None:
        with pytest.raises(ValidationError):
            ClassificationOutput(
                is_children_activity=False,
                is_toddler_friendly=False,
                confidence=1.5,
            )

    def test_confidence_out_of_range_low(self) -> None:
        with pytest.raises(ValidationError):
            ClassificationOutput(
                is_children_activity=False,
                is_toddler_friendly=False,
                confidence=-0.1,
            )


class TestLocationEnrichmentOutput:
    def test_valid_location(self) -> None:
        output = LocationEnrichmentOutput(
            normalized_address="Legazpi, 8",
            neighborhood="Arganzuela",
            metro="Legazpi",
        )

        assert output.normalized_address == "Legazpi, 8"
        assert output.neighborhood == "Arganzuela"
        assert output.metro == "Legazpi"

    def test_empty_neighborhood_and_metro(self) -> None:
        output = LocationEnrichmentOutput(
            normalized_address="Calle Mayor 1",
            neighborhood="",
            metro="",
        )

        assert output.neighborhood == ""
        assert output.metro == ""

    def test_defaults_for_optional_fields(self) -> None:
        output = LocationEnrichmentOutput(
            normalized_address="Gran Vía 10",
        )

        assert output.neighborhood == ""
        assert output.metro == ""
