from __future__ import annotations

import uuid
from datetime import UTC, datetime

from hazlo.application.services.review_engine import ReviewEngine
from hazlo.domain.event import Event, EventStatus, Location, Price, TicketInfo


def _make_event(
    title: str = "Test Event",
    start_at: datetime | None | bool = True,
    confidence: float | None = None,
    price: Price | None = None,
    ticket_info: TicketInfo | None = None,
) -> Event:
    actual_start_at: datetime | None
    if start_at is True:
        actual_start_at = datetime(2026, 6, 1, 20, 0, tzinfo=UTC)
    elif start_at is False:
        actual_start_at = None
    else:
        actual_start_at = start_at

    return Event(
        id=uuid.uuid4(),
        title=title,
        location=Location(address="Calle Mayor 1", neighborhood="Sol"),
        start_at=actual_start_at,
        end_at=datetime(2026, 6, 1, 22, 0, tzinfo=UTC),
        price=price or Price(is_free=True),
        ticket_info=ticket_info or TicketInfo(),
        source_url="https://example.com/1",
        extracted_at=datetime.now(UTC),
        confidence_score=confidence,
    )


def test_auto_approve_high_confidence() -> None:
    engine = ReviewEngine(auto_approve_threshold=0.95)
    event = _make_event(confidence=0.98)

    decision = engine.execute(event)

    assert decision.action == EventStatus.APPROVED
    assert "0.98" in decision.reason


def test_flag_medium_confidence() -> None:
    engine = ReviewEngine(auto_approve_threshold=0.95)
    event = _make_event(confidence=0.80)

    decision = engine.execute(event)

    assert decision.action == EventStatus.PENDING
    assert "review range" in decision.reason


def test_flag_low_confidence() -> None:
    engine = ReviewEngine(auto_approve_threshold=0.95)
    event = _make_event(confidence=0.50)

    decision = engine.execute(event)

    assert decision.action == EventStatus.PENDING
    assert "Low confidence" in decision.reason


def test_flag_no_confidence() -> None:
    engine = ReviewEngine(auto_approve_threshold=0.95)
    event = _make_event(confidence=None)

    decision = engine.execute(event)

    assert decision.action == EventStatus.PENDING
    assert "No confidence" in decision.reason


def test_flag_missing_title() -> None:
    engine = ReviewEngine(auto_approve_threshold=0.95)
    event = _make_event(title="")

    decision = engine.execute(event)

    assert decision.action == EventStatus.PENDING
    assert "title" in decision.reason


def test_flag_missing_start_at() -> None:
    engine = ReviewEngine(auto_approve_threshold=0.95)
    event = _make_event(start_at=False)

    decision = engine.execute(event)

    assert decision.action == EventStatus.PENDING
    assert "start_at" in decision.reason


def test_flag_paid_event_without_ticket_url() -> None:
    engine = ReviewEngine(auto_approve_threshold=0.95)
    event = _make_event(
        price=Price(amount_cents=1000, is_free=False),
        ticket_info=TicketInfo(url=None),
        confidence=0.98,
    )

    decision = engine.execute(event)

    assert decision.action == EventStatus.PENDING
    assert "ticket URL" in decision.reason


def test_custom_threshold() -> None:
    engine = ReviewEngine(auto_approve_threshold=0.90)
    event = _make_event(confidence=0.92)

    decision = engine.execute(event)

    assert decision.action == EventStatus.APPROVED
