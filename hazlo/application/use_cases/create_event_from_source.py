from __future__ import annotations

import uuid
from datetime import UTC, datetime

from hazlo.domain.event import Event, EventStatus, Location, Price, TicketInfo


class CreateEventFromSource:
    def __init__(self) -> None:
        pass

    def execute(
        self,
        *,
        title: str,
        source_id: uuid.UUID,
        source_url: str,
        external_id: str,
        location_address: str,
        location_neighborhood: str,
        location_metro_stop: str | None = None,
        start_time: datetime,
        end_time: datetime | None = None,
        price_amount: float | None = None,
        price_is_free: bool = False,
        ticket_url: str | None = None,
        is_children_activity: bool = False,
        is_toddler_friendly: bool = False,
    ) -> Event:
        location = Location(
            address=location_address,
            neighborhood=location_neighborhood,
            metro_stop=location_metro_stop,
        )
        price = Price(
            amount=price_amount,
            is_free=price_is_free,
        )
        ticket_info: TicketInfo | None = None
        if ticket_url:
            ticket_info = TicketInfo(url=ticket_url)

        event = Event(
            title=title,
            location=location,
            start_time=start_time,
            end_time=end_time,
            price=price,
            ticket_info=ticket_info,
            is_children_activity=is_children_activity,
            is_toddler_friendly=is_toddler_friendly,
            source_url=source_url,
            external_id=external_id,
            extraction_date=datetime.now(UTC),
            status=EventStatus.PENDING_REVIEW,
            source_id=source_id,
        )
        return event
