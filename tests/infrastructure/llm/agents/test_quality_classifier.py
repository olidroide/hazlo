from __future__ import annotations

import pytest
from pydantic_ai.models.test import TestModel

from hazlo.domain.event import Event, Location, Price
from hazlo.infrastructure.llm.agents.quality_classifier import QualityClassifierAgent


class TestQualityClassifierAgent:
    @pytest.mark.asyncio
    async def test_execute_returns_classification_result(self) -> None:
        model = TestModel()
        agent = QualityClassifierAgent(model)

        event = Event(
            title="Taller infantil de pintura",
            start_at=None,
            source_url="https://example.com/event",
            location=Location(address="Calle Mayor 1", neighborhood="Centro"),
            price=Price(is_free=True, amount_cents=0),
        )

        result = await agent.execute(event)

        assert isinstance(result.is_children_activity, bool)
        assert isinstance(result.is_toddler_friendly, bool)
        assert isinstance(result.confidence, float)
        assert 0.0 <= result.confidence <= 1.0
        assert result.raw_response != ""

    @pytest.mark.asyncio
    async def test_execute_handles_event_without_location(self) -> None:
        model = TestModel()
        agent = QualityClassifierAgent(model)

        event = Event(
            title="Concierto de jazz",
            start_at=None,
            source_url="https://example.com/event",
            location=None,
            price=None,
        )

        result = await agent.execute(event)

        assert isinstance(result.is_children_activity, bool)
        assert isinstance(result.confidence, float)

    @pytest.mark.asyncio
    async def test_execute_builds_prompt_with_all_fields(self) -> None:
        from datetime import datetime

        model = TestModel()
        agent = QualityClassifierAgent(model)

        event = Event(
            title="Cuentacuentos familiar",
            start_at=datetime(2025, 6, 15, 10, 0),
            end_at=datetime(2025, 6, 15, 12, 0),
            source_url="https://example.com/event",
            location=Location(address="Parque del Retiro", neighborhood="Retiro"),
            price=Price(is_free=False, amount_cents=500),
        )

        result = await agent.execute(event)

        assert result.confidence >= 0.0
        assert result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_execute_with_paid_event(self) -> None:
        model = TestModel()
        agent = QualityClassifierAgent(model)

        event = Event(
            title="Exposición de arte moderno",
            start_at=None,
            source_url="https://example.com/event",
            location=Location(address="Museo Reina Sofía", neighborhood="Lavapiés"),
            price=Price(is_free=False, amount_cents=1200),
        )

        result = await agent.execute(event)

        assert isinstance(result.is_children_activity, bool)
        assert isinstance(result.is_toddler_friendly, bool)
