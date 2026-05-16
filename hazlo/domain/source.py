from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class SourceType(Enum):
    WEB_SCRAPING = "web_scraping"
    API = "api"
    CSV = "csv"
    FEED = "feed"


class SourceStatus(Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"


@dataclass
class Source:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    name: str = ""
    source_type: SourceType = SourceType.WEB_SCRAPING
    url: str = ""
    status: SourceStatus = SourceStatus.ACTIVE
    extraction_frequency_minutes: int = 60
    last_run_at: datetime | None = None
    last_run_success: bool | None = None
    config: dict[str, str] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
