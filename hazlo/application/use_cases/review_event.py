from __future__ import annotations

import uuid

from hazlo.domain.event import Event, EventStatus
from hazlo.domain.review import Review, ReviewAction


class ReviewEvent:
    def execute(
        self,
        *,
        event: Event,
        reviewer_id: uuid.UUID,
        title: str | None = None,
        status: EventStatus,
        changes: dict[str, object] | None = None,
    ) -> tuple[Event, Review]:
        if title is not None:
            event.title = title

        event.status = status
        event.updated_at = event.updated_at

        action = ReviewAction.EDIT if title is not None else ReviewAction.APPROVE
        if status == EventStatus.REJECTED:
            action = ReviewAction.REJECT
        elif status == EventStatus.APPROVED and title is None:
            action = ReviewAction.APPROVE

        review = Review(
            event_id=event.id,
            reviewer_id=reviewer_id,
            action=action,
            changes=changes or {},
        )

        return event, review
