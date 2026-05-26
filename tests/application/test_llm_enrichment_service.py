"""Tests for LLMEnrichmentService - TDD strict."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from hazlo.application.services.llm_enrichment_service import LLMEnrichmentService
from hazlo.domain.event import Event, Location
from hazlo.infrastructure.llm.client import LLMResponse


@pytest.fixture
def mock_llm_client() -> MagicMock:
    """Mock LLMClient for testing."""
    client = MagicMock()
    client.generate = AsyncMock()
    return client


@pytest.fixture
def sample_event() -> Event:
    """Sample event with raw address."""
    return Event(
        title="Concierto de Jazz",
        location=Location(
            address="de Legazpi, 8",
            neighborhood="",
            metro=None,
        ),
        source_url="https://example.com/event",
        idempotency_key="test-key",
    )


class TestLLMEnrichmentService:
    """Test suite for LLMEnrichmentService."""

    @pytest.mark.asyncio
    async def test_enrich_location_partial_enrichment(self, mock_llm_client: MagicMock, sample_event: Event) -> None:
        """Test partial enrichment when LLM returns some empty fields."""
        # Arrange
        llm_response = LLMResponse(
            content=json.dumps(
                {
                    "normalized_address": "Gran Vía, 70",
                    "neighborhood": "Centro",
                    "metro": "",  # Empty - unknown
                }
            ),
            model="gemini-2.0-flash",
        )
        mock_llm_client.generate.return_value = llm_response
        service = LLMEnrichmentService(mock_llm_client)

        # Act
        enriched_event = await service.enrich_location(sample_event)

        # Assert
        assert enriched_event.location is not None
        assert enriched_event.location.address == "Gran Vía, 70"
        assert enriched_event.location.neighborhood == "Centro"
        assert enriched_event.location.metro is None  # Empty string → None

    @pytest.mark.asyncio
    async def test_enrich_location_invalid_json_returns_original(
        self, mock_llm_client: MagicMock, sample_event: Event
    ) -> None:
        """Test that invalid JSON response returns original event."""
        # Arrange
        llm_response = LLMResponse(
            content="This is not valid JSON",
            model="gemini-2.0-flash",
        )
        mock_llm_client.generate.return_value = llm_response
        service = LLMEnrichmentService(mock_llm_client)

        # Act
        enriched_event = await service.enrich_location(sample_event)

        # Assert - original values preserved
        assert enriched_event.location is not None
        assert enriched_event.location.address == "de Legazpi, 8"
        assert enriched_event.location.neighborhood == ""
        assert enriched_event.location.metro is None

    @pytest.mark.asyncio
    async def test_enrich_location_missing_fields_returns_original(
        self, mock_llm_client: MagicMock, sample_event: Event
    ) -> None:
        """Test that missing required fields returns original event."""
        # Arrange
        llm_response = LLMResponse(
            content=json.dumps(
                {
                    "normalized_address": "Some address",
                    # Missing neighborhood and metro
                }
            ),
            model="gemini-2.0-flash",
        )
        mock_llm_client.generate.return_value = llm_response
        service = LLMEnrichmentService(mock_llm_client)

        # Act
        enriched_event = await service.enrich_location(sample_event)

        # Assert - original values preserved due to incomplete response
        assert enriched_event.location is not None
        assert enriched_event.location.address == "de Legazpi, 8"
        assert enriched_event.location.neighborhood == ""
        assert enriched_event.location.metro is None

    @pytest.mark.asyncio
    async def test_enrich_location_no_location_returns_original(self, mock_llm_client: MagicMock) -> None:
        """Test that event without location returns unchanged."""
        # Arrange
        event = Event(
            title="Online Event",
            location=None,
            source_url="https://example.com/online",
            idempotency_key="test-key-online",
        )
        service = LLMEnrichmentService(mock_llm_client)

        # Act
        enriched_event = await service.enrich_location(event)

        # Assert
        assert enriched_event.location is None
        mock_llm_client.generate.assert_not_called()

    @pytest.mark.asyncio
    async def test_enrich_location_preserves_other_fields(
        self, mock_llm_client: MagicMock, sample_event: Event
    ) -> None:
        """Test that enrichment preserves non-location fields."""
        # Arrange
        llm_response = LLMResponse(
            content=json.dumps(
                {
                    "normalized_address": "Legazpi, 8",
                    "neighborhood": "Arganzuela",
                    "metro": "Legazpi",
                }
            ),
            model="gemini-2.0-flash",
        )
        mock_llm_client.generate.return_value = llm_response
        service = LLMEnrichmentService(mock_llm_client)

        # Act
        enriched_event = await service.enrich_location(sample_event)

        # Assert - other fields unchanged
        assert enriched_event.title == sample_event.title
        assert enriched_event.source_url == sample_event.source_url
