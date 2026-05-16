from __future__ import annotations

import uuid
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from decimal import Decimal
from enum import Enum


class EventStatus(Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    PUBLISHED = "published"


ALLOWED_TRANSITIONS: dict[EventStatus, set[EventStatus]] = {
    EventStatus.PENDING: {EventStatus.APPROVED, EventStatus.REJECTED},
    EventStatus.APPROVED: {EventStatus.PUBLISHED},
    EventStatus.REJECTED: set(),
    EventStatus.PUBLISHED: set(),
}


class InvalidTransitionError(Exception):
    pass


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

    def can_transition_to(self, new_status: EventStatus) -> bool:
        return new_status in ALLOWED_TRANSITIONS.get(self.status, set())

    def with_status(self, new_status: EventStatus) -> Event:
        if not self.can_transition_to(new_status):
            raise InvalidTransitionError(f"Cannot transition from {self.status.value} to {new_status.value}")
        return replace(self, status=new_status, updated_at=datetime.now(UTC))

    def with_changes(self, **kwargs: object) -> Event:
        return replace(self, **kwargs, updated_at=datetime.now(UTC))

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "location": {
                "address": self.location.address,
                "neighborhood": self.location.neighborhood,
                "metro": self.location.metro,
            }
            if self.location
            else None,
            "start_at": self.start_at,
            "end_at": self.end_at,
            "price": {
                "amount": str(self.price.amount) if self.price.amount else None,
                "is_free": self.price.is_free,
                "notes": self.price.notes,
            }
            if self.price
            else None,
            "ticket_info": {
                "url": self.ticket_info.url,
                "notes": self.ticket_info.notes,
            }
            if self.ticket_info
            else None,
            "is_children_activity": self.is_children_activity,
            "is_toddler_friendly": self.is_toddler_friendly,
            "status": self.status.value,
        }

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
