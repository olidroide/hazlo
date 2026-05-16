from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum


class EventStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"


@dataclass(frozen=True)
class Location:
    address: str
    neighborhood: str
    metro: str | None = None


@dataclass(frozen=True)
class Price:
    amount: Decimal | None = None
    is_free: bool = False
    notes: str | None = None


@dataclass(frozen=True)
class TicketInfo:
    url: str | None = None
    notes: str | None = None


@dataclass
class Event:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    title: str = ""
    location: Location | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    price: Price | None = None
    ticket_info: TicketInfo | None = None
    is_children_activity: bool = False
    is_toddler_friendly: bool = False
    source_url: str = ""
    extracted_at: datetime | None = None
    status: EventStatus = EventStatus.PENDING
    source_id: uuid.UUID | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def requires_ticket_url(self) -> bool:
        if self.price is None:
            return False
        return not self.price.is_free

    def is_valid(self) -> bool:
        if not self.title:
            return False
        if self.start_at is None:
            return False
        return not (self.requires_ticket_url() and (self.ticket_info is None or not self.ticket_info.url))
