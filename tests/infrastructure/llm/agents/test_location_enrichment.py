from __future__ import annotations

import pytest
from pydantic_ai.models.test import TestModel

from hazlo.domain.event import Event, Location
from hazlo.infrastructure.llm.agents.location_enrichment import LocationEnrichmentAgent


class TestLocationEnrichmentAgent:
    @pytest.mark.asyncio
    async def test_enrich_location_returns_enriched_event(self) -> None:
        model = TestModel()
        agent = LocationEnrichmentAgent(model)

        event = Event(
            title="Concierto en el parque",
            start_at=None,
            source_url="https://example.com/event",
            location=Location(address="de Legazpi, 8", neighborhood=""),
        )

        result = await agent.enrich_location(event)

        assert result.location is not None
        assert isinstance(result.location.address, str)
        assert isinstance(result.location.neighborhood, str)

    @pytest.mark.asyncio
    async def test_enrich_location_returns_original_when_no_location(self) -> None:
        model = TestModel()
        agent = LocationEnrichmentAgent(model)

        event = Event(
            title="Evento sin ubicación",
            start_at=None,
            source_url="https://example.com/event",
            location=None,
        )

        result = await agent.enrich_location(event)

        assert result.location is None
        assert result.title == event.title

    @pytest.mark.asyncio
    async def test_enrich_location_preserves_event_fields(self) -> None:
        model = TestModel()
        agent = LocationEnrichmentAgent(model)

        event = Event(
            title="Taller de cocina",
            start_at=None,
            source_url="https://example.com/event",
            location=Location(address="Calle Alcalá 123", neighborhood="Salamanca"),
        )

        result = await agent.enrich_location(event)

        assert result.title == event.title
        assert result.source_url == event.source_url

    @pytest.mark.asyncio
    async def test_enrich_location_with_existing_neighborhood(self) -> None:
        model = TestModel()
        agent = LocationEnrichmentAgent(model)

        event = Event(
            title="Exposición fotográfica",
            start_at=None,
            source_url="https://example.com/event",
            location=Location(address="Gran Vía 45", neighborhood="Centro"),
        )

        result = await agent.enrich_location(event)

        assert result.location is not None

    @pytest.mark.asyncio
    async def test_enrich_location_with_metro_station(self) -> None:
        model = TestModel()
        agent = LocationEnrichmentAgent(model)

        event = Event(
            title="Mercadillo vintage",
            start_at=None,
            source_url="https://example.com/event",
            location=Location(address="Plaza de España", neighborhood=""),
        )

        result = await agent.enrich_location(event)

        assert result.location is not None
