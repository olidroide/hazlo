from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from hazlo.application.use_cases.review_event import ReviewEvent
from hazlo.domain.event import Event, EventStatus, InvalidTransitionError, Location, Price, TicketInfo
from hazlo.domain.review import ReviewAction


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
    return Event(**{k: v for k, v in defaults.items()})


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
    diff = review.changes["title"]
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
