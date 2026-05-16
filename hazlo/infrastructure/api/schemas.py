from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class SourceCreate(BaseModel):
    model_config = ConfigDict(strict=True)

    name: str
    source_type: str
    url: str
    fetch_interval_minutes: int = 60


class SourceResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    name: str
    source_type: str
    url: str
    is_active: bool
    fetch_interval_minutes: int
    last_run_at: datetime | None = None
    last_run_status: str | None = None


class EventReviewRequest(BaseModel):
    model_config = ConfigDict(strict=True)

    action: str
    changes: dict | None = None


class EventResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    title: str
    status: str
    source_url: str
    is_children_activity: bool
    is_toddler_friendly: bool


class ExtractionRunResponse(BaseModel):
    model_config = ConfigDict(strict=True)

    id: uuid.UUID
    source_id: uuid.UUID
    started_at: datetime
    finished_at: datetime | None
    status: str
    events_found: int
    errors: str | None = None
