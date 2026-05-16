from __future__ import annotations

import uuid

from hazlo.domain.event import Event, EventStatus
from hazlo.domain.review import Review


class ReviewEvent:
    def __init__(self) -> None:
        pass

    def execute(
        self,
        *,
        event: Event,
        reviewer_id: uuid.UUID,
        title: str | None = None,
        status: EventStatus,
        changes: dict[str, str] | None = None,
        notes: str | None = None,
    ) -> tuple[Event, Review]:
        if title is not None:
            event.title = title

        event.status = status
        event.updated_at = event.updated_at

        review = Review(
            event_id=event.id,
            reviewer_id=reviewer_id,
            changes=changes or {},
            notes=notes,
        )

        return event, review
