from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, cast

import pytest

from hazlo.application.use_cases.review_event import ReviewEvent
from hazlo.domain.event import Event, EventStatus, InvalidTransitionError, Location, Price, TicketInfo
from hazlo.domain.review import ReviewAction

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
    source_id: uuid.UUID | object = _NOT_SET,
) -> Event:
    kwargs: dict[str, Any] = {
        "id": uuid.uuid4() if id is _NOT_SET else id,
        "title": title,
        "location": location
        if location is not _NOT_SET
        else Location(address="Calle Mayor 1", neighborhood="Centro", metro="Sol"),
        "start_at": start_at if start_at is not _NOT_SET else datetime(2026, 6, 1, 20, 0, tzinfo=UTC),
        "end_at": end_at if end_at is not _NOT_SET else datetime(2026, 6, 1, 22, 0, tzinfo=UTC),
        "price": price if price is not _NOT_SET else Price(amount_cents=1000, is_free=False, notes=None),
        "ticket_info": ticket_info
        if ticket_info is not _NOT_SET
        else TicketInfo(url="https://tickets.example.com", notes=None),
        "is_children_activity": is_children_activity,
        "is_toddler_friendly": is_toddler_friendly,
        "source_url": source_url,
        "extracted_at": extracted_at if extracted_at is not _NOT_SET else datetime(2026, 5, 16, 10, 0, tzinfo=UTC),
        "status": status,
    }
    if source_id is not _NOT_SET:
        kwargs["source_id"] = source_id
    return Event(**{k: v for k, v in kwargs.items()})


def test_approve_pending_event_changes_status() -> None:
    event = _make_event(status=EventStatus.PENDING)
    use_case = ReviewEvent()
    updated, review = use_case.execute(
        event=event,
        reviewer_id=uuid.uuid4(),
        action="approve",
    )
    assert updated.status == EventStatus.APPROVED
    assert review.action == ReviewAction.APPROVE
    assert "status" in review.changes


def test_reject_pending_event_changes_status() -> None:
    event = _make_event(status=EventStatus.PENDING)
    use_case = ReviewEvent()
    updated, review = use_case.execute(
        event=event,
        reviewer_id=uuid.uuid4(),
        action="reject",
    )
    assert updated.status == EventStatus.REJECTED
    assert review.action == ReviewAction.REJECT
    assert "status" in review.changes


def test_cannot_reject_already_rejected_event() -> None:
    event = _make_event(status=EventStatus.REJECTED)
    use_case = ReviewEvent()
    with pytest.raises(InvalidTransitionError):
        use_case.execute(
            event=event,
            reviewer_id=uuid.uuid4(),
            action="reject",
        )


def test_edit_captures_diff_in_review() -> None:
    event = _make_event(status=EventStatus.PENDING, title="Original Title")
    use_case = ReviewEvent()
    _updated, review = use_case.execute(
        event=event,
        reviewer_id=uuid.uuid4(),
        action="edit",
        changes={"title": "New Title"},
    )
    assert review.action == ReviewAction.EDIT
    assert "title" in review.changes
    diff = cast(dict[str, str], review.changes["title"])
    assert diff["before"] == "Original Title"
    assert diff["after"] == "New Title"


def test_invalid_transition_raises_domain_error() -> None:
    event = _make_event(status=EventStatus.APPROVED)
    use_case = ReviewEvent()
    with pytest.raises(InvalidTransitionError):
        use_case.execute(
            event=event,
            reviewer_id=uuid.uuid4(),
            action="reject",
        )


def test_approved_can_transition_to_published() -> None:
    event = _make_event(status=EventStatus.APPROVED)
    use_case = ReviewEvent()
    updated, review = use_case.execute(
        event=event,
        reviewer_id=uuid.uuid4(),
        action="publish",
    )
    assert updated.status == EventStatus.PUBLISHED
    assert review.action == ReviewAction.APPROVE
