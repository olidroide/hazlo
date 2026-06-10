"""Tests for ReparseEventAgent using TestModel."""

from __future__ import annotations

import pytest
from pydantic_ai.models.test import TestModel

from hazlo.infrastructure.llm.agents.reparse_event import ReparseEventAgent


@pytest.mark.asyncio
async def test_reparse_agent_returns_valid_output() -> None:
    model = TestModel()
    agent = ReparseEventAgent(model, retries=1)

    output = await agent.reparse(
        raw_payload={"title": "Jazz Night", "source_url": "https://example.com"},
        raw_body="<service><name>Concierto de Jazz</name><body>Jazz en Madrid</body></service>",
        existing_event={"title": "Jazz Night", "location": {"address": "Unknown"}},
    )

    assert isinstance(output.title, str)
    assert isinstance(output.address, str)
    assert isinstance(output.neighborhood, str)
    assert 0.0 <= output.confidence <= 1.0
    assert isinstance(output.field_confidence, dict)
    assert len(output.field_confidence) > 0


@pytest.mark.asyncio
async def test_reparse_agent_handles_empty_raw_body() -> None:
    model = TestModel()
    agent = ReparseEventAgent(model, retries=1)

    output = await agent.reparse(
        raw_payload={"title": "Test"},
        raw_body="",
        existing_event={"title": "Test"},
    )

    assert isinstance(output.title, str)
