from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class ReviewAction(Enum):
    APPROVE = "approve"
    REJECT = "reject"
    EDIT = "edit"


@dataclass
class Review:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    reviewer_id: uuid.UUID | None = None
    action: ReviewAction = ReviewAction.APPROVE
    changes: dict[str, object] = field(default_factory=dict)
    reviewed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
