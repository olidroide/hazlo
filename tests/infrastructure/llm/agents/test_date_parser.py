"""Tests for DateParserAgent - TDD strict."""

from __future__ import annotations

import pytest
from pydantic_ai import ModelResponse
from pydantic_ai.messages import ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from hazlo.domain.event import Event, Location
from hazlo.infrastructure.llm.agents import DateParserAgent


def create_mock_model(
    start_at: str | None = None,
    end_at: str | None = None,
    confidence: float = 0.9,
    fail: bool = False,
) -> FunctionModel:
    """Create a FunctionModel that returns structured date parsing output."""

    def mock_generate(messages: list, info: AgentInfo) -> ModelResponse:
        if fail:
            raise ConnectionError("Mock model failure")

        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="final_result",
                    args={
                        "start_at": start_at,
                        "end_at": end_at,
                        "confidence": confidence,
                    },
                )
            ]
        )

    return FunctionModel(mock_generate)


@pytest.fixture
def sample_event() -> Event:
    """Sample event with bad XML dates."""
    return Event(
        title="Euphoria Art is in the Air",
        location=Location(
            address="del Embarcadero, Recinto Ferial",
            neighborhood="Madrid",
        ),
        source_url="https://example.com/event",
        idempotency_key="test-key",
    )


class TestDateParserAgent:
    """Test suite for DateParserAgent."""

    @pytest.mark.asyncio
    async def test_parse_dates_corrects_bad_xml_dates(self, sample_event: Event) -> None:
        """Test that LLM corrects bad XML dates."""
        model = create_mock_model(
            start_at="2026-06-19T18:30:00+02:00",
            end_at="2026-09-06T22:00:00+02:00",
            confidence=0.95,
        )
        agent = DateParserAgent(model)

        result = await agent.parse_dates(sample_event)

        assert result.start_at is not None
        assert "2026-06-19" in result.start_at.isoformat()
        assert result.end_at is not None
        assert "2026-09-06" in result.end_at.isoformat()

    @pytest.mark.asyncio
    async def test_parse_dates_low_confidence_keeps_original(self, sample_event: Event) -> None:
        """Test that low confidence keeps original dates."""
        model = create_mock_model(
            start_at="2026-06-19T18:30:00+02:00",
            confidence=0.1,
        )
        agent = DateParserAgent(model)

        result = await agent.parse_dates(sample_event)

        assert result is sample_event

    @pytest.mark.asyncio
    async def test_parse_dates_failing_model_returns_original(self, sample_event: Event) -> None:
        """Test that failing model returns original event."""
        model = create_mock_model(fail=True)
        agent = DateParserAgent(model, retries=1)

        result = await agent.parse_dates(sample_event)

        assert result is sample_event

    @pytest.mark.asyncio
    async def test_parse_dates_no_delta_returns_original(self, sample_event: Event) -> None:
        """Test that when LLM returns same dates, original event is returned."""
        model = create_mock_model(
            start_at=None,
            end_at=None,
            confidence=0.9,
        )
        agent = DateParserAgent(model)

        result = await agent.parse_dates(sample_event)

        assert result is sample_event

    @pytest.mark.asyncio
    async def test_parse_dates_single_day_event(self, sample_event: Event) -> None:
        """Test single-day event parsing."""
        model = create_mock_model(
            start_at="2026-06-19T20:00:00+02:00",
            end_at=None,
            confidence=0.9,
        )
        agent = DateParserAgent(model)

        result = await agent.parse_dates(sample_event)

        assert result.start_at is not None
        assert result.end_at is None
