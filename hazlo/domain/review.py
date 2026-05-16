from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class ReviewAction(Enum):
    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"


class InvalidTransitionError(Exception):
    pass


@dataclass
class Review:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    reviewer_id: uuid.UUID | None = None
    action: ReviewAction = ReviewAction.APPROVE
    changes: dict[str, object] = field(default_factory=dict)
    reviewed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @staticmethod
    def compute_diff(before: dict[str, object], after: dict[str, object]) -> dict[str, object]:
        diff: dict[str, object] = {}
        all_keys = set(before.keys()) | set(after.keys())
        for key in all_keys:
            before_val = before.get(key)
            after_val = after.get(key)
            if before_val != after_val:
                diff[key] = {"before": before_val, "after": after_val}
        return diff
