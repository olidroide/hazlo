from __future__ import annotations

import uuid

from hazlo.domain.event import Event, EventStatus
from hazlo.domain.review import InvalidTransitionError, Review, ReviewAction

VALID_ACTIONS: dict[str, EventStatus] = {
    "approve": EventStatus.APPROVED,
    "reject": EventStatus.REJECTED,
    "publish": EventStatus.PUBLISHED,
}


class ReviewEvent:
    def execute(
        self,
        *,
        event: Event,
        reviewer_id: uuid.UUID,
        action: str,
        changes: dict[str, object] | None = None,
    ) -> tuple[Event, Review]:
        target_status = VALID_ACTIONS.get(action)

        if action == "edit":
            if not event.can_transition_to(EventStatus.APPROVED) and not event.can_transition_to(EventStatus.REJECTED):
                raise InvalidTransitionError(f"Cannot edit event in {event.status.value} status")
            updated = event
            if changes:
                updated = event.with_changes(**changes)
            before = event.to_dict()
            after = updated.to_dict()
            diff = Review.compute_diff(before, after)
            review = Review(
                event_id=event.id,
                reviewer_id=reviewer_id,
                action=ReviewAction.EDIT,
                changes=diff,
            )
            return updated, review

        if target_status is None:
            msg = f"Invalid action: {action}"
            raise ValueError(msg)

        updated = event.with_status(target_status)
        before = event.to_dict()
        after = updated.to_dict()
        if changes:
            after.update(changes)
        diff = Review.compute_diff(before, after)

        review_action = ReviewAction.APPROVE if action in ("approve", "publish") else ReviewAction.REJECT
        review = Review(
            event_id=event.id,
            reviewer_id=reviewer_id,
            action=review_action,
            changes=diff,
        )
        return updated, review
