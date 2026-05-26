from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class SourceType(Enum):
    RSS = "rss"
    WEB = "web"
    EMAIL = "email"


class SourceStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


@dataclass
class Source:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    name: str = ""
    source_type: SourceType = SourceType.RSS
    url: str | None = None
    config: dict = field(default_factory=dict)
    is_active: bool = True
    fetch_interval_minutes: int = 60
    last_run_at: datetime | None = None
    last_run_status: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
