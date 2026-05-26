from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import ClassVar, cast

from hazlo.domain.event import Location, Price, TicketInfo


class EnrichmentService:
    """Deterministic: normalize dates, prices, addresses. Extract metro from lookup table."""

    METRO_LOOKUP: ClassVar[dict[str, str]] = {
        "sol": "Sol",
        "gran via": "Gran Via",
        "callao": "Callao",
        "tribunal": "Tribunal",
        "alonso martinez": "Alonso Martinez",
        "colon": "Colon",
        "retiro": "Retiro",
        "chueca": "Chueca",
        "malasana": "Tribunal",
        "lavapiés": "Lavapies",
        "lavapies": "Lavapies",
        "chamberi": "Iglesia",
        "salamanca": "Velazquez",
        "arganzuela": "Mendez Alvaro",
        "moncloa": "Moncloa",
        "tetuan": "Tetuan",
        "fuencarral": "Tribunal",
    }

    def execute(self, raw_event: dict) -> dict:
        """Input: raw event dict. Output: enriched event dict.

        No side effects. No DB access. No LLM calls.
        """
        enriched = dict(raw_event)

        enriched["title"] = self._normalize_title(enriched.get("title", ""))
        enriched["description"] = self._normalize_description(enriched.get("description", ""))
        enriched["start_at"] = self._normalize_datetime(enriched.get("start_at"))
        enriched["end_at"] = self._normalize_datetime(enriched.get("end_at"))
        enriched["price"] = self._normalize_price(enriched.get("price"))
        enriched["location"] = self._normalize_location(enriched.get("location"))
        enriched["ticket_info"] = self._normalize_ticket_info(enriched.get("ticket_info"))
        enriched["category"] = self._infer_category(enriched)

        return enriched

    def _normalize_title(self, title: str) -> str:
        if not title:
            return ""
        title = re.sub(r"\s+", " ", title.strip())
        return title[:200]

    def _normalize_description(self, description: str) -> str:
        if not description:
            return ""
        description = re.sub(r"\s+", " ", description.strip())
        return description[:2000]

    def _normalize_datetime(self, value: object) -> datetime | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value if value.tzinfo else value.replace(tzinfo=UTC)
        if isinstance(value, str):
            for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%d/%m/%Y %H:%M", "%d/%m/%Y"):
                try:
                    dt = datetime.strptime(value, fmt)
                    return dt.replace(tzinfo=UTC)
                except ValueError:
                    continue
        return None

    def _normalize_price(self, value: object) -> Price:
        if value is None:
            return Price(is_free=True)
        if isinstance(value, Price):
            return value
        if isinstance(value, dict):
            _value = cast(dict[str, object], value)
            amount_cents_raw = _value.get("amount_cents")
            amount_cents = int(cast(int, amount_cents_raw)) if amount_cents_raw is not None else None
            return Price(
                amount_cents=amount_cents,
                is_free=bool(_value.get("is_free", False)),
                notes=cast(str | None, _value.get("notes")),
            )
        if isinstance(value, str):
            lower = value.lower().strip()
            if not lower or lower in ("gratis", "gratuito", "free", "0", "0.00", "0,00"):
                return Price(is_free=True)
            match = re.search(r"(\d+[,.]\d{2})\s*€", value)
            if match:
                amount_str = match.group(1).replace(",", ".")
                return Price(amount_cents=round(float(amount_str) * 100))
            match = re.search(r"([\d]{1,3}(?:[.]\d{3})+)\s*€", value)
            if match:
                amount_str = match.group(1).replace(".", "")
                return Price(amount_cents=int(amount_str) * 100)
            match = re.search(r"(\d+)\s*€", value)
            if match:
                return Price(amount_cents=int(match.group(1)) * 100)
            return Price(is_free=True)
        if isinstance(value, int):
            return Price(amount_cents=value) if value > 0 else Price(is_free=True)
        if isinstance(value, float):
            return Price(amount_cents=round(value * 100)) if value > 0 else Price(is_free=True)
        return Price(is_free=True)

    def _normalize_location(self, value: object) -> Location | None:
        if value is None:
            return None
        if isinstance(value, Location):
            return value
        if isinstance(value, str):
            address = value.strip()
            if not address:
                return None
            neighborhood = self._extract_neighborhood(address)
            metro = self._lookup_metro(address)
            return Location(address=address, neighborhood=neighborhood, metro=metro)
        if isinstance(value, dict):
            _value = cast(dict[str, str], value)
            address = _value.get("address", "").strip()
            if not address:
                return None
            neighborhood = _value.get("neighborhood") or self._extract_neighborhood(address)
            metro = _value.get("metro") or self._lookup_metro(address)
            return Location(address=address, neighborhood=neighborhood, metro=metro)
        return None

    def _normalize_ticket_info(self, value: object) -> TicketInfo | None:
        if value is None:
            return None
        if isinstance(value, TicketInfo):
            return value
        if isinstance(value, str):
            return TicketInfo(url=value.strip() if value.strip() else None)
        if isinstance(value, dict):
            _value = cast(dict[str, str | None], value)
            url_str = _value.get("url")
            url = url_str.strip() if url_str else None
            notes = _value.get("notes")
            return TicketInfo(url=url, notes=notes)
        return None

    def _extract_neighborhood(self, address: str) -> str:
        address_lower = address.lower()
        for hood in [
            "malasana",
            "chueca",
            "lavapies",
            "lavapiés",
            "salamanca",
            "chamberi",
            "arganzuela",
            "retiro",
            "moncloa",
            "tetuan",
            "fuencarral",
            "sol",
            "colon",
        ]:
            if hood in address_lower:
                return hood.title()
        return ""

    def _lookup_metro(self, address: str) -> str | None:
        address_lower = address.lower()
        for key, metro in self.METRO_LOOKUP.items():
            if key in address_lower:
                return metro
        return None

    def _infer_category(self, enriched: dict) -> str:
        title = (enriched.get("title") or "").lower()
        description = (enriched.get("description") or "").lower()
        text = f"{title} {description}"

        if any(kw in text for kw in ["taller", "workshop", "curso", "clase"]):
            return "workshop"
        if any(kw in text for kw in ["concierto", "musica", "festival", "dj"]):
            return "music"
        if any(kw in text for kw in ["exposicion", "museo", "galeria", "arte"]):
            return "exhibition"
        if any(kw in text for kw in ["teatro", "obra", "drama", "comedia"]):
            return "theater"
        if any(kw in text for kw in ["cine", "pelicula", "film", "documental"]):
            return "cinema"
        if any(kw in text for kw in ["deporte", "running", "yoga", "partido"]):
            return "sports"
        if any(kw in text for kw in ["mercado", "feria", "food", "gastronom"]):
            return "food_market"
        return "general"
