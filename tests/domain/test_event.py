from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from hazlo.domain.event import Event, EventStatus, Location, Price, TicketInfo


def _make_event(**kwargs: object) -> Event:
    defaults: dict[str, object] = {
        "id": uuid.uuid4(),
        "title": "Test Event",
        "location": Location(address="Calle Mayor 1", neighborhood="Centro", metro="Sol"),
        "start_at": datetime(2026, 6, 1, 20, 0, tzinfo=UTC),
        "end_at": datetime(2026, 6, 1, 22, 0, tzinfo=UTC),
        "price": Price(amount=Decimal("10.00"), is_free=False, notes=None),
        "ticket_info": TicketInfo(url="https://tickets.example.com", notes=None),
        "is_children_activity": False,
        "is_toddler_friendly": False,
        "source_url": "https://source.example.com/event",
        "extracted_at": datetime(2026, 5, 16, 10, 0, tzinfo=UTC),
        "status": EventStatus.PENDING,
    }
    defaults.update(kwargs)
    return Event(**defaults)


def test_event_requires_ticket_url_when_paid() -> None:
    event = _make_event(
        price=Price(amount=Decimal("15.00"), is_free=False, notes=None),
        ticket_info=TicketInfo(url=None, notes=None),
    )
    assert event.requires_ticket_url() is True
    assert event.is_valid() is False


def test_event_is_invalid_without_title() -> None:
    event = _make_event(title="")
    assert event.is_valid() is False


def test_free_event_does_not_require_ticket_url() -> None:
    event = _make_event(
        price=Price(amount=None, is_free=True, notes="Free entry"),
        ticket_info=TicketInfo(url=None, notes=None),
    )
    assert event.requires_ticket_url() is False
    assert event.is_valid() is True


def test_event_is_valid_with_all_required_fields() -> None:
    event = _make_event()
    assert event.is_valid() is True


def test_event_is_invalid_without_start_at() -> None:
    event = _make_event(start_at=None)
    assert event.is_valid() is False


def test_paid_event_without_ticket_url_is_invalid() -> None:
    event = _make_event(
        price=Price(amount=Decimal("5.00"), is_free=False, notes=None),
        ticket_info=TicketInfo(url=None, notes=None),
    )
    assert event.requires_ticket_url() is True
    assert event.is_valid() is False
