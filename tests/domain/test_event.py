from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import cast

from hazlo.domain.event import Event, EventStatus, Location, Price, TicketInfo

_NOT_SET = object()


def _make_event(
    id: uuid.UUID | object = _NOT_SET,
    title: str = "Test Event",
    location: Location | object = _NOT_SET,
    start_at: datetime | object = _NOT_SET,
    end_at: datetime | object = _NOT_SET,
    price: Price | object = _NOT_SET,
    ticket_info: TicketInfo | object = _NOT_SET,
    is_children_activity: bool = False,
    is_toddler_friendly: bool = False,
    source_url: str = "https://source.example.com/event",
    extracted_at: datetime | object = _NOT_SET,
    status: EventStatus = EventStatus.PENDING,
) -> Event:
    return Event(
        id=cast(uuid.UUID, uuid.uuid4() if id is _NOT_SET else id),
        title=title,
        location=cast(
            Location,
            location
            if location is not _NOT_SET
            else Location(address="Calle Mayor 1", neighborhood="Centro", metro="Sol"),
        ),
        start_at=cast(datetime, start_at if start_at is not _NOT_SET else datetime(2026, 6, 1, 20, 0, tzinfo=UTC)),
        end_at=cast(datetime, end_at if end_at is not _NOT_SET else datetime(2026, 6, 1, 22, 0, tzinfo=UTC)),
        price=cast(Price, price if price is not _NOT_SET else Price(amount_cents=1000, is_free=False, notes=None)),
        ticket_info=cast(
            TicketInfo,
            ticket_info if ticket_info is not _NOT_SET else TicketInfo(url="https://tickets.example.com", notes=None),
        ),
        is_children_activity=is_children_activity,
        is_toddler_friendly=is_toddler_friendly,
        source_url=source_url,
        extracted_at=cast(
            datetime, extracted_at if extracted_at is not _NOT_SET else datetime(2026, 5, 16, 10, 0, tzinfo=UTC)
        ),
        status=status,
    )


def test_event_valid_even_when_paid_without_ticket_url() -> None:
    event = _make_event(
        price=Price(amount_cents=1500, is_free=False, notes=None),
        ticket_info=TicketInfo(url=None, notes=None),
    )
    assert event.requires_ticket_url() is True
    assert event.is_valid() is True


def test_event_is_invalid_without_title() -> None:
    event = _make_event(title="")
    assert event.is_valid() is False


def test_free_event_does_not_require_ticket_url() -> None:
    event = _make_event(
        price=Price(amount_cents=None, is_free=True, notes="Free entry"),
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


def test_paid_event_without_ticket_url_is_still_valid() -> None:
    event = _make_event(
        price=Price(amount_cents=500, is_free=False, notes=None),
        ticket_info=TicketInfo(url=None, notes=None),
    )
    assert event.requires_ticket_url() is True
    assert event.is_valid() is True
