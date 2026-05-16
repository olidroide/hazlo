from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from hazlo.domain.event import Event, EventStatus, Location, Price, TicketInfo


class CreateEventFromSource:
    def execute(
        self,
        *,
        title: str,
        source_id: uuid.UUID,
        source_url: str,
        location_address: str,
        location_neighborhood: str,
        location_metro: str | None = None,
        start_at: datetime,
        end_at: datetime | None = None,
        price_amount: Decimal | None = None,
        price_is_free: bool = False,
        ticket_url: str | None = None,
        is_children_activity: bool = False,
        is_toddler_friendly: bool = False,
    ) -> Event:
        location = Location(
            address=location_address,
            neighborhood=location_neighborhood,
            metro=location_metro,
        )
        price = Price(
            amount=price_amount,
            is_free=price_is_free,
        )
        ticket_info: TicketInfo | None = None
        if ticket_url:
            ticket_info = TicketInfo(url=ticket_url)

        return Event(
            title=title,
            location=location,
            start_at=start_at,
            end_at=end_at,
            price=price,
            ticket_info=ticket_info,
            is_children_activity=is_children_activity,
            is_toddler_friendly=is_toddler_friendly,
            source_url=source_url,
            extracted_at=datetime.now(UTC),
            status=EventStatus.PENDING,
            source_id=source_id,
        )
