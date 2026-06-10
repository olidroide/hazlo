"""Use case: manually edit an event."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, replace
from datetime import UTC, datetime

from hazlo.domain.event import Event, Location, Price, TicketInfo
from hazlo.domain.review import Review, ReviewAction


@dataclass
class EditEventCommand:
    title: str | None = None
    description: str | None = None
    address: str | None = None
    neighborhood: str | None = None
    metro: str | None = None
    start_at: datetime | None = None
    end_at: datetime | None = None
    price_amount_cents: int | None = None
    is_free: bool | None = None
    price_notes: str | None = None
    ticket_url: str | None = None
    ticket_notes: str | None = None
    is_children_activity: bool | None = None
    is_toddler_friendly: bool | None = None


@dataclass
class EditEventResult:
    event: Event
    review: Review
    fields_changed: list[str]


class EditEvent:
    def execute(self, event: Event, command: EditEventCommand) -> EditEventResult:
        updated = self._apply_edit(event, command)
        fields_changed = self._compute_delta(event, updated)

        review = Review(
            id=uuid.uuid4(),
            event_id=event.id,
            reviewer_id=uuid.uuid4(),
            action=ReviewAction.EDIT,
            changes={
                f: {"before": self._serialize(getattr(event, f)), "after": self._serialize(getattr(updated, f))}
                for f in fields_changed
            },
            reviewed_at=datetime.now(UTC),
        )

        return EditEventResult(
            event=updated,
            review=review,
            fields_changed=fields_changed,
        )

    @staticmethod
    def _apply_edit(event: Event, command: EditEventCommand) -> Event:
        location = event.location
        if location is None and (command.address or command.neighborhood):
            location = Location(
                address=command.address or "",
                neighborhood=command.neighborhood or "",
                metro=command.metro,
            )
        elif location:
            location = replace(
                location,
                address=command.address if command.address is not None else location.address,
                neighborhood=command.neighborhood if command.neighborhood is not None else location.neighborhood,
                metro=command.metro if command.metro is not None else location.metro,
            )

        price = event.price
        if price is None:
            price = Price(
                amount_cents=command.price_amount_cents,
                is_free=command.is_free or False,
                notes=command.price_notes,
            )
        else:
            price = replace(
                price,
                amount_cents=command.price_amount_cents
                if command.price_amount_cents is not None
                else price.amount_cents,
                is_free=command.is_free if command.is_free is not None else price.is_free,
                notes=command.price_notes if command.price_notes is not None else price.notes,
            )

        ticket_info = event.ticket_info
        if ticket_info is None:
            ticket_info = TicketInfo(
                url=command.ticket_url,
                notes=command.ticket_notes,
            )
        else:
            ticket_info = replace(
                ticket_info,
                url=command.ticket_url if command.ticket_url is not None else ticket_info.url,
                notes=command.ticket_notes if command.ticket_notes is not None else ticket_info.notes,
            )

        return replace(
            event,
            title=command.title if command.title is not None else event.title,
            description=command.description if command.description is not None else event.description,
            location=location,
            start_at=command.start_at if command.start_at is not None else event.start_at,
            end_at=command.end_at if command.end_at is not None else event.end_at,
            price=price,
            ticket_info=ticket_info,
            is_children_activity=command.is_children_activity
            if command.is_children_activity is not None
            else event.is_children_activity,
            is_toddler_friendly=command.is_toddler_friendly
            if command.is_toddler_friendly is not None
            else event.is_toddler_friendly,
            updated_at=datetime.now(UTC),
        )

    @staticmethod
    def _compute_delta(old: Event, new: Event) -> list[str]:
        changed = []
        for field_name in (
            "title",
            "description",
            "location",
            "start_at",
            "end_at",
            "price",
            "ticket_info",
            "is_children_activity",
            "is_toddler_friendly",
        ):
            if getattr(old, field_name) != getattr(new, field_name):
                changed.append(field_name)
        return changed

    @staticmethod
    def _serialize(value: object) -> str:
        if value is None:
            return ""
        return str(value)
