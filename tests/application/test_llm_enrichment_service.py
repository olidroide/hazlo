"""Tests for LocationEnrichmentAgent - TDD strict."""

from __future__ import annotations

import pytest
from pydantic_ai import ModelResponse
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from hazlo.domain.event import Event, Location
from hazlo.infrastructure.llm.agents import LocationEnrichmentAgent


def create_mock_model(
    normalized_address: str = "Legazpi, 8",
    neighborhood: str = "Arganzuela",
    metro: str = "Legazpi",
    fail: bool = False,
) -> FunctionModel:
    """Create a FunctionModel that returns structured location enrichment output."""

    def mock_generate(messages: list, info: AgentInfo) -> ModelResponse:
        if fail:
            raise ConnectionError("Mock model failure")

        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="final_result",
                    args={
                        "normalized_address": normalized_address,
                        "neighborhood": neighborhood,
                        "metro": metro,
                    },
                )
            ]
        )

    return FunctionModel(mock_generate)


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


class TestLocationEnrichmentAgent:
    """Test suite for LocationEnrichmentAgent."""

    @pytest.mark.asyncio
    async def test_enrich_location_partial_enrichment(self, sample_event: Event) -> None:
        """Test partial enrichment when LLM returns some empty fields."""
        model = create_mock_model(
            normalized_address="Gran Vía, 70",
            neighborhood="Centro",
            metro="",
        )
        agent = LocationEnrichmentAgent(model)

        enriched_event = await agent.enrich_location(sample_event)

        assert enriched_event.location is not None
        assert enriched_event.location.address == "Gran Vía, 70"
        assert enriched_event.location.neighborhood == "Centro"
        assert enriched_event.location.metro is None

    @pytest.mark.asyncio
    async def test_enrich_location_full_enrichment(self, sample_event: Event) -> None:
        """Test full enrichment when LLM returns all fields."""
        model = create_mock_model(
            normalized_address="Legazpi, 8",
            neighborhood="Arganzuela",
            metro="Legazpi",
        )
        agent = LocationEnrichmentAgent(model)

        enriched_event = await agent.enrich_location(sample_event)

        assert enriched_event.location is not None
        assert enriched_event.location.address == "Legazpi, 8"
        assert enriched_event.location.neighborhood == "Arganzuela"
        assert enriched_event.location.metro == "Legazpi"

    @pytest.mark.asyncio
    async def test_enrich_location_no_location_returns_original(self) -> None:
        """Test that event without location returns unchanged."""
        event = Event(
            title="Online Event",
            location=None,
            source_url="https://example.com/online",
            idempotency_key="test-key-online",
        )
        model = create_mock_model()
        agent = LocationEnrichmentAgent(model)

        enriched_event = await agent.enrich_location(event)

        assert enriched_event.location is None

    @pytest.mark.asyncio
    async def test_enrich_location_preserves_other_fields(self, sample_event: Event) -> None:
        """Test that enrichment preserves non-location fields."""
        model = create_mock_model(
            normalized_address="Legazpi, 8",
            neighborhood="Arganzuela",
            metro="Legazpi",
        )
        agent = LocationEnrichmentAgent(model)

        enriched_event = await agent.enrich_location(sample_event)

        assert enriched_event.title == sample_event.title
        assert enriched_event.source_url == sample_event.source_url

    @pytest.mark.asyncio
    async def test_enrich_location_with_failing_model(self, sample_event: Event) -> None:
        """Test that failing model returns original event."""
        model = create_mock_model(fail=True)
        agent = LocationEnrichmentAgent(model, retries=1)

        enriched_event = await agent.enrich_location(sample_event)

        assert enriched_event.location is not None
        assert enriched_event.location.address == "de Legazpi, 8"
        assert enriched_event.location.neighborhood == ""
        assert enriched_event.location.metro is None
