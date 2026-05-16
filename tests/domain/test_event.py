from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from hazlo.domain.event import Event, EventStatus, Location, Price, TicketInfo

_UNSET = object()


def _make_event(
    id: uuid.UUID | None | object = _UNSET,
    title: str = "Test Event",
    location: Location | None | object = _UNSET,
    start_at: datetime | None | object = _UNSET,
    end_at: datetime | None | object = _UNSET,
    price: Price | None | object = _UNSET,
    ticket_info: TicketInfo | None | object = _UNSET,
    is_children_activity: bool = False,
    is_toddler_friendly: bool = False,
    source_url: str = "https://source.example.com/event",
    extracted_at: datetime | None | object = _UNSET,
    status: EventStatus = EventStatus.PENDING,
) -> Event:
    return Event(
        id=uuid.uuid4() if id is _UNSET else id,
        title=title,
        location=location
        if location is not _UNSET
        else Location(address="Calle Mayor 1", neighborhood="Centro", metro="Sol"),
        start_at=start_at if start_at is not _UNSET else datetime(2026, 6, 1, 20, 0, tzinfo=UTC),
        end_at=end_at if end_at is not _UNSET else datetime(2026, 6, 1, 22, 0, tzinfo=UTC),
        price=price if price is not _UNSET else Price(amount=Decimal("10.00"), is_free=False, notes=None),
        ticket_info=ticket_info
        if ticket_info is not _UNSET
        else TicketInfo(url="https://tickets.example.com", notes=None),
        is_children_activity=is_children_activity,
        is_toddler_friendly=is_toddler_friendly,
        source_url=source_url,
        extracted_at=extracted_at if extracted_at is not _UNSET else datetime(2026, 5, 16, 10, 0, tzinfo=UTC),
        status=status,
    )


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
