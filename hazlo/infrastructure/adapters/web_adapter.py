from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from hazlo.domain.event import Event, Location, Price, TicketInfo
from hazlo.domain.source import Source
from hazlo.infrastructure.adapters.base import BaseSourceAdapter


class WebSourceAdapter(BaseSourceAdapter):
    async def fetch(self, source: Source) -> list[dict]:
        if not source.url:
            return []

        raise NotImplementedError(
            "WebSourceAdapter not yet implemented. "
            "Configure selectors in source.config and implement httpx + justhtml parsing."
        )

    async def normalize(self, raw: dict) -> Event:
        start_raw = raw.get("start_at")
        end_raw = raw.get("end_at")
        start_at = datetime.fromisoformat(start_raw) if start_raw else None
        end_at = datetime.fromisoformat(end_raw) if end_raw else None
        price_amount_raw = raw.get("price_amount")
        price_amount = Decimal(price_amount_raw) if price_amount_raw else None

        return Event(
            id=uuid.uuid4(),
            title=raw["title"],
            location=Location(
                address=raw.get("address", ""),
                neighborhood=raw.get("neighborhood", ""),
                metro=raw.get("metro"),
            ),
            start_at=start_at,
            end_at=end_at,
            price=Price(
                amount_cents=int(price_amount * 100) if price_amount is not None else None,
                is_free=raw.get("is_free", False),
                notes=raw.get("price_notes"),
            ),
            ticket_info=TicketInfo(
                url=raw.get("ticket_url"),
                notes=raw.get("ticket_notes"),
            ),
            is_children_activity=raw.get("is_children_activity", False),
            is_toddler_friendly=raw.get("is_toddler_friendly", False),
            source_url=raw["source_url"],
            extracted_at=datetime.now(UTC),
        )
