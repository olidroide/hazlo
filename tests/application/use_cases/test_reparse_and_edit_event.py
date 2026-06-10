"""Tests for ReparseEvent and EditEvent use cases."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from hazlo.application.use_cases.edit_event import EditEvent, EditEventCommand
from hazlo.application.use_cases.reparse_event import RawDocForReparse, ReparseEvent
from hazlo.domain.event import Event, Location, Price, TicketInfo
from hazlo.domain.llm_output import ReparseEventOutput


class FakeRawStore:
    def __init__(self, doc: RawDocForReparse) -> None:
        self._doc = doc

    def read(self, event_id: uuid.UUID) -> RawDocForReparse:
        return self._doc


class FakeReparseAgent:
    def __init__(self, output: ReparseEventOutput) -> None:
        self._output = output

    async def reparse(
        self,
        raw_payload: dict[str, object],
        raw_body: str,
        existing_event: dict[str, object],
    ) -> ReparseEventOutput:
        return self._output


def _make_event() -> Event:
    return Event(
        id=uuid.uuid4(),
        title="Old Title",
        description="Old description",
        location=Location(address="Old St 1", neighborhood="Old Barrio", metro="Old Metro"),
        start_at=datetime(2026, 6, 1, 20, 0, tzinfo=UTC),
        end_at=datetime(2026, 6, 1, 22, 0, tzinfo=UTC),
        price=Price(amount_cents=1000, is_free=False, notes="Old notes"),
        ticket_info=TicketInfo(url="https://old.com", notes="Old ticket"),
        is_children_activity=False,
        is_toddler_friendly=False,
        source_url="https://example.com",
        extracted_at=datetime(2026, 5, 16, 10, 0, tzinfo=UTC),
    )


@pytest.mark.asyncio
async def test_reparse_event_updates_fields() -> None:
    output = ReparseEventOutput(
        title="New Title",
        description="New description",
        address="New St 1",
        neighborhood="New Barrio",
        metro="New Metro",
        start_at="2026-07-01T19:00:00+02:00",
        end_at="2026-07-01T21:00:00+02:00",
        price_amount_cents=2000,
        is_free=False,
        price_notes="New notes",
        ticket_url="https://new.com",
        ticket_notes="New ticket",
        is_children_activity=True,
        is_toddler_friendly=False,
        confidence=0.9,
        field_confidence={
            "title": 0.9,
            "description": 0.9,
            "location": 0.9,
            "dates": 0.9,
            "price": 0.9,
            "ticket": 0.9,
            "classification": 0.9,
        },
        reasoning="Test reparse",
    )

    event = _make_event()
    raw_doc = RawDocForReparse(payload={"title": "Raw Title"}, body=b"<raw/>")
    store = FakeRawStore(raw_doc)
    agent = FakeReparseAgent(output)

    use_case = ReparseEvent(agent=agent, raw_store=store)
    result = await use_case.execute(event)

    assert result.event.title == "New Title"
    assert result.event.location is not None
    assert result.event.location.address == "New St 1"
    assert result.event.is_children_activity is True
    assert len(result.fields_changed) > 0
    assert result.reasoning == "Test reparse"


@pytest.mark.asyncio
async def test_reparse_event_creates_review() -> None:
    output = ReparseEventOutput(
        title="New Title",
        description=None,
        address="New St 1",
        neighborhood="",
        metro=None,
        start_at=None,
        end_at=None,
        price_amount_cents=None,
        is_free=True,
        price_notes=None,
        ticket_url=None,
        ticket_notes=None,
        is_children_activity=False,
        is_toddler_friendly=False,
        confidence=0.8,
        field_confidence={
            "title": 0.9,
            "description": 0.9,
            "location": 0.9,
            "dates": 0.9,
            "price": 0.9,
            "ticket": 0.9,
            "classification": 0.9,
        },
        reasoning="Test",
    )

    event = _make_event()
    raw_doc = RawDocForReparse(payload={}, body=b"")
    store = FakeRawStore(raw_doc)
    agent = FakeReparseAgent(output)

    use_case = ReparseEvent(agent=agent, raw_store=store)
    result = await use_case.execute(event)

    assert result.review.event_id == event.id
    assert len(result.review.changes) > 0


def test_edit_event_updates_fields() -> None:
    event = _make_event()
    command = EditEventCommand(
        title="Edited Title",
        address="Edited St 1",
        is_children_activity=True,
    )

    use_case = EditEvent()
    result = use_case.execute(event, command)

    assert result.event.title == "Edited Title"
    assert result.event.location is not None
    assert result.event.location.address == "Edited St 1"
    assert result.event.is_children_activity is True
    assert "title" in result.fields_changed
    assert "location" in result.fields_changed


def test_edit_event_creates_review() -> None:
    event = _make_event()
    command = EditEventCommand(title="Edited")

    use_case = EditEvent()
    result = use_case.execute(event, command)

    assert result.review.event_id == event.id
    assert "title" in result.review.changes


def test_edit_event_no_changes_returns_empty_delta() -> None:
    event = _make_event()
    command = EditEventCommand()

    use_case = EditEvent()
    result = use_case.execute(event, command)

    assert result.fields_changed == []
