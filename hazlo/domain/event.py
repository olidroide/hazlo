from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
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
class IdempotencyKey:
    """Deterministic key for exactly-once event ingestion.

    Computed from source_url + normalized title + start_at.
    Same event from same source always produces same key.
    """

    value: str

    @classmethod
    def from_event(cls, source_url: str, title: str, start_at: datetime | None) -> IdempotencyKey:
        normalized_title = re.sub(r"\s+", " ", title.lower().strip())
        start_str = start_at.isoformat() if start_at else ""
        raw = f"{source_url}|{normalized_title}|{start_str}"
        return cls(hashlib.sha256(raw.encode("utf-8")).hexdigest())


@dataclass(frozen=True)
class Location:
    address: str
    neighborhood: str
    metro: str | None = None


@dataclass(frozen=True)
class Price:
    """Stripe-style pricing: amount stored in smallest currency unit (cents for EUR)."""

    amount_cents: int | None = None
    is_free: bool = False
    notes: str | None = None

    @property
    def amount_euros(self) -> float | None:
        if self.amount_cents is None:
            return None
        return self.amount_cents / 100

    @classmethod
    def from_euros(cls, euros: float) -> Price:
        return cls(amount_cents=round(euros * 100))


@dataclass(frozen=True)
class TicketInfo:
    url: str | None = None
    notes: str | None = None


@dataclass
class Event:
    id: uuid.UUID = field(default_factory=uuid.uuid4)
    title: str = ""
    raw_title: str = ""
    description: str = ""
    raw_description: str = ""
    location: Location | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    price: Price | None = None
    ticket_info: TicketInfo | None = None
    is_children_activity: bool = False
    is_toddler_friendly: bool = False
    confidence_score: float | None = None
    agent_review: dict | None = None
    source_url: str = ""
    extracted_at: datetime | None = None
    status: EventStatus = EventStatus.PENDING
    source_id: uuid.UUID | None = None
    idempotency_key: str | None = None
    content_hash: str | None = None
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
            "raw_title": self.raw_title,
            "description": self.description,
            "raw_description": self.raw_description,
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
                "amount_cents": self.price.amount_cents,
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
            "confidence_score": self.confidence_score,
            "agent_review": self.agent_review,
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
        return self.location is not None

    def compute_idempotency_key(self) -> IdempotencyKey:
        return IdempotencyKey.from_event(self.source_url, self.title, self.start_at)

    @staticmethod
    def normalize_for_hash(raw_event: Mapping[str, object]) -> dict[str, object]:
        """Normalize fields to prevent false negatives in dedup.

        Normalizes whitespace, case, and accents to ensure equivalent events
        produce the same hash regardless of formatting differences.
        """
        def normalize_text(text: object) -> object:
            if not isinstance(text, str):
                return text
            text = re.sub(r"\s+", " ", text.strip().lower())
            return text

        def normalize_datetime(dt_str: object) -> object:
            if not isinstance(dt_str, str):
                return dt_str
            try:
                dt_str_normalized = dt_str.replace("Z", "+00:00")
                dt = datetime.fromisoformat(dt_str_normalized)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=UTC)
                return dt.isoformat()
            except ValueError:
                return dt_str

        return {
            "title": normalize_text(raw_event.get("title")),
            "description": normalize_text(raw_event.get("description")),
            "location": normalize_text(raw_event.get("location")),
            "start_at": normalize_datetime(raw_event.get("start_at")),
            "end_at": normalize_datetime(raw_event.get("end_at")),
            "price": normalize_text(raw_event.get("price")),
            "ticket_info": raw_event.get("ticket_info"),
        }

    @staticmethod
    def compute_content_hash(raw_event: Mapping[str, object]) -> str:
        """Compute SHA-256 hash of normalized event content for deduplication.

        Hashes only content fields (title, description, location, start_at, end_at, price, ticket_info).
        Normalizes whitespace, case, and datetime formats before hashing.
        Ignores metadata fields (extracted_at, source_url) that don't represent event content.

        Args:
            raw_event: Raw event dictionary from adapter

        Returns:
            SHA-256 hex digest (64 characters)
        """
        normalized = Event.normalize_for_hash(raw_event)
        content_json = json.dumps(normalized, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(content_json.encode("utf-8")).hexdigest()
