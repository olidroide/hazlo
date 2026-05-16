from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum


class EventStatus(Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"


@dataclass(frozen=True)
class Location:
    address: str
    neighborhood: str
    metro_stop: str | None = None


@dataclass(frozen=True)
class Price:
    amount: float | None = None
    is_free: bool = False
    discount_info: str | None = None


@dataclass(frozen=True)
class TicketInfo:
    url: str | None = None
    point_of_sale: str | None = None
    notes: str | None = None


@dataclass
class Event:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    title: str = ""
    location: Location | None = None
    start_time: datetime | None = None
    end_time: datetime | None = None
    price: Price | None = None
    ticket_info: TicketInfo | None = None
    is_children_activity: bool = False
    is_toddler_friendly: bool = False
    source_url: str | None = None
    external_id: str | None = None
    extraction_date: datetime | None = None
    status: EventStatus = EventStatus.PENDING_REVIEW
    source_id: uuid.UUID | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
