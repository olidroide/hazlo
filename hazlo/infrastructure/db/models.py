from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from hazlo.domain.event import Event, EventStatus, Location, Price, TicketInfo
from hazlo.domain.review import Review, ReviewAction
from hazlo.domain.source import Source, SourceType


def _utcnow() -> datetime:
    return datetime.now(UTC)


class Base(DeclarativeBase):
    pass


class EventModel(Base):
    __tablename__ = "events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    location: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    start_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    price: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    ticket_info: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)
    is_children_activity: Mapped[bool] = mapped_column(Boolean, default=False)
    is_toddler_friendly: Mapped[bool] = mapped_column(Boolean, default=False)
    source_url: Mapped[str] = mapped_column(String(1000), nullable=False)
    extracted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="pending")
    source_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("sources.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class SourceModel(Base):
    __tablename__ = "sources"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[str] = mapped_column(String(30), nullable=False, default="scraper")
    url: Mapped[str] = mapped_column(String(1000), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    fetch_interval_minutes: Mapped[int] = mapped_column(Integer, default=60)
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_run_status: Mapped[str | None] = mapped_column(String(30), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)


class ExtractionRunModel(Base):
    __tablename__ = "extraction_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("sources.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="running")
    events_found: Mapped[int] = mapped_column(Integer, default=0)
    errors: Mapped[str | None] = mapped_column(Text, nullable=True)


class ReviewModel(Base):
    __tablename__ = "reviews"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    event_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("events.id"), nullable=False)
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    changes: Mapped[dict[str, object]] = mapped_column(JSONB, default=dict)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)


def _location_to_dict(location: Location) -> dict[str, object]:
    return {
        "address": location.address,
        "neighborhood": location.neighborhood,
        "metro": location.metro,
    }


def _dict_to_location(data: dict[str, object]) -> Location:
    metro_raw = data.get("metro")
    return Location(
        address=str(data["address"]),
        neighborhood=str(data["neighborhood"]),
        metro=str(metro_raw) if metro_raw is not None else None,
    )


def _price_to_dict(price: Price) -> dict[str, object]:
    return {
        "amount": str(price.amount) if price.amount is not None else None,
        "is_free": price.is_free,
        "notes": price.notes,
    }


def _dict_to_price(data: dict[str, object]) -> Price:
    raw_amount = data.get("amount")
    amount = Decimal(str(raw_amount)) if raw_amount is not None else None
    notes_raw = data.get("notes")
    return Price(
        amount=amount,
        is_free=bool(data.get("is_free", False)),
        notes=str(notes_raw) if notes_raw is not None else None,
    )


def _ticket_info_to_dict(ticket_info: TicketInfo) -> dict[str, object]:
    return {
        "url": ticket_info.url,
        "notes": ticket_info.notes,
    }


def _dict_to_ticket_info(data: dict[str, object]) -> TicketInfo:
    url_raw = data.get("url")
    notes_raw = data.get("notes")
    return TicketInfo(
        url=str(url_raw) if url_raw is not None else None,
        notes=str(notes_raw) if notes_raw is not None else None,
    )


def event_to_model(event: Event) -> EventModel:
    if event.location is None:
        msg = "Event location is required"
        raise ValueError(msg)
    if event.price is None:
        msg = "Event price is required"
        raise ValueError(msg)
    if event.ticket_info is None:
        msg = "Event ticket_info is required"
        raise ValueError(msg)
    if event.start_at is None:
        msg = "Event start_at is required"
        raise ValueError(msg)
    if event.extracted_at is None:
        msg = "Event extracted_at is required"
        raise ValueError(msg)

    return EventModel(
        id=event.id,
        title=event.title,
        location=_location_to_dict(event.location),
        start_at=event.start_at,
        end_at=event.end_at,
        price=_price_to_dict(event.price),
        ticket_info=_ticket_info_to_dict(event.ticket_info),
        is_children_activity=event.is_children_activity,
        is_toddler_friendly=event.is_toddler_friendly,
        source_url=event.source_url,
        extracted_at=event.extracted_at,
        status=event.status.value,
        source_id=event.source_id,
        created_at=event.created_at,
        updated_at=event.updated_at,
    )


def model_to_event(model: EventModel) -> Event:
    return Event(
        id=model.id,
        title=model.title,
        location=_dict_to_location(model.location),
        start_at=model.start_at,
        end_at=model.end_at,
        price=_dict_to_price(model.price),
        ticket_info=_dict_to_ticket_info(model.ticket_info),
        is_children_activity=model.is_children_activity,
        is_toddler_friendly=model.is_toddler_friendly,
        source_url=model.source_url,
        extracted_at=model.extracted_at,
        status=EventStatus(model.status),
        source_id=model.source_id,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def source_to_model(source: Source) -> SourceModel:
    return SourceModel(
        id=source.id,
        name=source.name,
        source_type=source.source_type.value,
        url=source.url,
        is_active=source.is_active,
        fetch_interval_minutes=source.fetch_interval_minutes,
        last_run_at=source.last_run_at,
        last_run_status=source.last_run_status,
        created_at=source.created_at,
        updated_at=source.updated_at,
    )


def model_to_source(model: SourceModel) -> Source:
    return Source(
        id=model.id,
        name=model.name,
        source_type=SourceType(model.source_type),
        url=model.url,
        is_active=model.is_active,
        fetch_interval_minutes=model.fetch_interval_minutes,
        last_run_at=model.last_run_at,
        last_run_status=model.last_run_status,
        created_at=model.created_at,
        updated_at=model.updated_at,
    )


def review_to_model(review: Review) -> ReviewModel:
    return ReviewModel(
        id=review.id,
        event_id=review.event_id,
        reviewer_id=review.reviewer_id,
        action=review.action.value,
        changes=review.changes,
        reviewed_at=review.reviewed_at,
    )


def model_to_review(model: ReviewModel) -> Review:
    return Review(
        id=model.id,
        event_id=model.event_id,
        reviewer_id=model.reviewer_id,
        action=ReviewAction(model.action),
        changes=model.changes,
        reviewed_at=model.reviewed_at,
    )
