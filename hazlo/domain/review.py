from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class Review:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    event_id: uuid.UUID = field(default_factory=uuid.uuid4)
    reviewer_id: uuid.UUID | None = None
    changes: dict[str, str] = field(default_factory=dict)
    notes: str | None = None
    reviewed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
