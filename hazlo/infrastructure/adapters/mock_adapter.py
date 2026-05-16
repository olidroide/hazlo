from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from hazlo.domain.event import Event, Location, Price, TicketInfo
from hazlo.infrastructure.adapters.base import BaseSourceAdapter

_FAKE_EVENTS: list[dict] = [
    {
        "title": "Concierto de Jazz en el Matadero",
        "address": "Paseo de la Chopera, 14",
        "neighborhood": "Arganzuela",
        "metro": "Legazpi",
        "start_at": "2026-06-15T20:00:00+02:00",
        "end_at": "2026-06-15T22:30:00+02:00",
        "price_amount": "15.00",
        "is_free": False,
        "price_notes": None,
        "ticket_url": "https://matadero.com/entradas/jazz",
        "ticket_notes": None,
        "is_children_activity": False,
        "is_toddler_friendly": False,
        "source_url": "https://matadero.com/evento/jazz-2026",
    },
    {
        "title": "Taller de pintura para familias",
        "address": "Calle de Fuencarral, 120",
        "neighborhood": "Chueca",
        "metro": "Tribunal",
        "start_at": "2026-07-01T11:00:00+02:00",
        "end_at": "2026-07-01T13:00:00+02:00",
        "price_amount": None,
        "is_free": True,
        "price_notes": "Entrada libre hasta completar aforo",
        "ticket_url": None,
        "ticket_notes": "No requiere reserva",
        "is_children_activity": True,
        "is_toddler_friendly": True,
        "source_url": "https://centrocultural.es/taller-pintura-familias",
    },
    {
        "title": "Exposición: Madrid Futuro",
        "address": "Calle de Alcalá, 50",
        "neighborhood": "Centro",
        "metro": "Banco de España",
        "start_at": "2026-08-10T10:00:00+02:00",
        "end_at": "2026-08-10T20:00:00+02:00",
        "price_amount": "8.50",
        "is_free": False,
        "price_notes": "Reducida menores de 18 años",
        "ticket_url": "https://museo.es/entradas/madrid-futuro",
        "ticket_notes": "Venta online y presencial",
        "is_children_activity": True,
        "is_toddler_friendly": False,
        "source_url": "https://museo.es/exposiciones/madrid-futuro-2026",
    },
]


class MockSourceAdapter(BaseSourceAdapter):
    async def fetch(self, source_url: str) -> list[dict]:
        return _FAKE_EVENTS

    async def normalize(self, raw: dict) -> Event:
        start_raw = raw.get("start_at", "")
        end_raw = raw.get("end_at", "")
        start_at = datetime.fromisoformat(start_raw) if start_raw else None
        end_at = datetime.fromisoformat(end_raw) if end_raw else None
        price_amount_raw = raw.get("price_amount")
        price_amount = Decimal(price_amount_raw) if price_amount_raw else None

        return Event(
            id=uuid.uuid4(),
            title=raw["title"],
            location=Location(
                address=raw["address"],
                neighborhood=raw["neighborhood"],
                metro=raw.get("metro"),
            ),
            start_at=start_at,
            end_at=end_at,
            price=Price(
                amount=price_amount,
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
