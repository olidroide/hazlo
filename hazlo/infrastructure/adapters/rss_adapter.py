from __future__ import annotations

import html
import logging
import re
import time
import uuid
from datetime import UTC, datetime, timedelta
from xml.etree import ElementTree
from xml.etree.ElementTree import Element

import httpx

from hazlo.domain.event import Event, Location, Price, TicketInfo
from hazlo.domain.source import Source
from hazlo.infrastructure.adapters.base import BaseSourceAdapter
from hazlo.settings import get_settings

_XML_NS = {"atom": "http://www.w3.org/2005/Atom"}
_DATE_FORMAT = "%d/%m/%Y"
_PRICE_PATTERN = re.compile(r"([\d]{1,3}(?:[.]\d{3})*[,.]\d{2})\s*€")
_PRICE_PATTERN_NO_DECIMALS = re.compile(r"([\d]{1,3}(?:[.]\d{3})*)\s*€")
_TIME_PATTERN = re.compile(r"(\d{1,2}:\d{2})\s*h")
_TAG_RE = re.compile(r"<[^>]+>")
_MIN_VALID_YEAR = 2015

_MONTHS_ES = {
    "enero": 1,
    "ene": 1,
    "febrero": 2,
    "feb": 2,
    "marzo": 3,
    "mar": 3,
    "abril": 4,
    "abr": 4,
    "mayo": 5,
    "may": 5,
    "junio": 6,
    "jun": 6,
    "julio": 7,
    "jul": 7,
    "agosto": 8,
    "ago": 8,
    "septiembre": 9,
    "sep": 9,
    "setiembre": 9,
    "octubre": 10,
    "oct": 10,
    "noviembre": 11,
    "nov": 11,
    "diciembre": 12,
    "dic": 12,
}

_ES_DATE_RANGE = re.compile(
    r"(?:d[ií]as?\s+)?(\d{1,2})"
    r"(?:\s+y\s+\d{1,2})?"
    r"\s+de\s+(\w+)"
    r"(?:\s+de\s+(\d{4}))?",
    re.IGNORECASE,
)

logger = logging.getLogger(__name__)


def _clean_text(text: str) -> str:
    return _TAG_RE.sub("", html.unescape(text)).strip()


class RssSourceAdapter(BaseSourceAdapter):
    async def fetch(self, source: Source) -> list[dict]:
        if not source.url:
            logger.warning("RSS source %s has no URL", source.id)
            return []

        verify = get_settings().verify_ssl
        t0 = time.monotonic()
        async with httpx.AsyncClient(timeout=30.0, verify=verify) as client:
            resp = await client.get(source.url)
            resp.raise_for_status()
        logger.info(
            "RSS fetched source=%s status=%d bytes=%d in %.1fms",
            source.id,
            resp.status_code,
            len(resp.text),
            (time.monotonic() - t0) * 1000,
        )

        parse_t0 = time.monotonic()
        root = ElementTree.fromstring(resp.text)  # noqa: S314
        all_services = root.findall(".//service")
        max_results = max(get_settings().rss_max_results, 1)
        services = _select_recent_services(all_services, max_results)
        logger.info(
            "RSS services selected source=%s total=%d selected=%d max_results=%d parse_ms=%.1f",
            source.id,
            len(all_services),
            len(services),
            max_results,
            (time.monotonic() - parse_t0) * 1000,
        )

        results = []
        for service in services:
            basic = service.find("basicData")
            geo = service.find("geoData")
            extra = service.find("extradata")

            if basic is None:
                continue

            name_elem = basic.find("name")
            title_elem = basic.find("title")
            web_elem = basic.find("web")
            body_elem = basic.find("body")
            venue_elem = basic.find("nombrert")

            address = ""
            locality = ""
            if geo is not None:
                addr_elem = geo.find("address")
                if addr_elem is not None and addr_elem.text:
                    address = html.unescape(addr_elem.text.strip())
                sub_admin = geo.find("subAdministrativeArea")
                if sub_admin is not None and sub_admin.text:
                    locality = html.unescape(sub_admin.text.strip())

            schedule_text = ""
            price_text = ""
            start_date_str = ""
            end_date_str = ""
            categories = []

            if extra is not None:
                for item in extra.findall("item"):
                    item_name = item.get("name", "")
                    if item_name == "Horario" and item.text:
                        schedule_text = html.unescape(item.text.strip())
                    elif item_name == "Servicios de pago" and item.text:
                        price_text = html.unescape(item.text.strip())

                dates_elem = extra.find("fechas")
                if dates_elem is not None:
                    range_elem = dates_elem.find("rango")
                    if range_elem is not None:
                        start_elem = range_elem.find("inicio")
                        end_elem = range_elem.find("fin")
                        if start_elem is not None and start_elem.text:
                            start_date_str = start_elem.text.strip()
                        if end_elem is not None and end_elem.text:
                            end_date_str = end_elem.text.strip()

                cats_elem = extra.find("categorias")
                if cats_elem is not None:
                    for cat in cats_elem.findall(".//categoria/item"):
                        if cat.get("name") == "Categoria" and cat.text:
                            categories.append(html.unescape(cat.text.strip()))
                    for subcat in cats_elem.findall(".//subcategoria/item"):
                        if subcat.get("name") == "SubCategoria" and subcat.text:
                            categories.append(html.unescape(subcat.text.strip()))

            title_raw = ""
            title = ""
            if title_elem is not None and title_elem.text:
                title_raw = html.unescape(title_elem.text.strip())
                title = _clean_text(title_elem.text.strip())
            elif name_elem is not None and name_elem.text:
                title_raw = html.unescape(name_elem.text.strip())
                title = _clean_text(name_elem.text.strip())

            source_url = ""
            if web_elem is not None and web_elem.text:
                source_url = web_elem.text.strip()

            venue = ""
            if venue_elem is not None and venue_elem.text:
                venue = html.unescape(venue_elem.text.strip())

            description_raw = ""
            description = ""
            if body_elem is not None and body_elem.text:
                description_raw = html.unescape(body_elem.text.strip())
                description = _clean_text(body_elem.text.strip())

            start_at, end_at = _parse_dates(start_date_str, end_date_str, schedule_text)

            price_amount_cents, is_free, price_notes = _parse_price(price_text)

            results.append(
                {
                    "title": title,
                    "raw_title": title_raw,
                    "address": address,
                    "neighborhood": locality,
                    "metro": None,
                    "venue": venue,
                    "start_at": start_at,
                    "end_at": end_at,
                    "price_amount_cents": price_amount_cents,
                    "is_free": is_free,
                    "price_notes": price_notes,
                    "ticket_url": None,
                    "ticket_notes": None,
                    "is_children_activity": False,
                    "is_toddler_friendly": False,
                    "source_url": source_url,
                    "description": description,
                    "raw_description": description_raw,
                    "categories": categories,
                }
            )

        return results

    async def normalize(self, raw: dict) -> Event:
        start_raw = raw.get("start_at")
        end_raw = raw.get("end_at")
        start_at = datetime.fromisoformat(start_raw) if start_raw else None
        end_at = datetime.fromisoformat(end_raw) if end_raw else None
        price_amount_cents = raw.get("price_amount_cents")
        is_free = raw.get("is_free", False)
        if not is_free and price_amount_cents is None:
            is_free = True

        return Event(
            id=uuid.uuid4(),
            title=raw["title"],
            raw_title=raw.get("raw_title", ""),
            description=raw.get("description", ""),
            raw_description=raw.get("raw_description", ""),
            location=Location(
                address=raw.get("address", ""),
                neighborhood=raw.get("neighborhood", ""),
                metro=raw.get("metro"),
            ),
            start_at=start_at,
            end_at=end_at,
            price=Price(
                amount_cents=price_amount_cents,
                is_free=is_free,
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


def _select_recent_services(services: list[Element], max_results: int) -> list[Element]:
    if len(services) <= max_results:
        return services

    return sorted(services, key=_service_sort_key, reverse=True)[:max_results]


def _service_sort_key(service: Element) -> datetime:
    extra = service.find("extradata")
    if extra is not None:
        dates_elem = extra.find("fechas")
        if dates_elem is not None:
            range_elem = dates_elem.find("rango")
            if range_elem is not None:
                start_elem = range_elem.find("inicio")
                if start_elem is not None and start_elem.text:
                    parsed = _try_parse_date(start_elem.text.strip())
                    if parsed is not None:
                        return parsed

    updated_at = service.get("fechaActualizacion")
    if updated_at:
        try:
            return datetime.strptime(updated_at, "%Y-%m-%d")
        except ValueError:
            pass

    return datetime.min


def _parse_dates(start_date: str | None, end_date: str | None, schedule: str | None) -> tuple[str | None, str | None]:
    if not start_date:
        return None, None

    date_obj = _try_parse_date(start_date)
    if date_obj is None:
        return None, None

    if date_obj.year < _MIN_VALID_YEAR:
        return None, None

    time_match = _TIME_PATTERN.search(schedule or "")
    if time_match:
        raw_hour = int(time_match.group(1).split(":")[0])
        raw_minute = int(time_match.group(1).split(":")[1])
        day_offset = raw_hour // 24
        hour = raw_hour % 24
        minute = min(raw_minute, 59)
        if day_offset:
            date_obj = date_obj + timedelta(days=day_offset)
    else:
        hour, minute = 0, 0

    start_dt = date_obj.replace(
        hour=hour,
        minute=minute,
        tzinfo=UTC,
    )

    end_dt = None
    if end_date and end_date != start_date:
        end_date_obj = _try_parse_date(end_date)
        if end_date_obj and end_date_obj.year >= _MIN_VALID_YEAR:
            end_dt = end_date_obj.replace(hour=start_dt.hour, minute=start_dt.minute, tzinfo=UTC)

    return start_dt.isoformat(), end_dt.isoformat() if end_dt else None


def _try_parse_date(text: str) -> datetime | None:
    try:
        return datetime.strptime(text, _DATE_FORMAT)
    except ValueError:
        pass

    match = _ES_DATE_RANGE.search(text)
    if match:
        day_str = match.group(1)
        month_name = match.group(2).lower()
        year_str = match.group(3)
        month = _MONTHS_ES.get(month_name)
        if month:
            year = int(year_str) if year_str else datetime.now(UTC).year
            try:
                return datetime(int(year), month, int(day_str))
            except ValueError:
                pass

    return None


def _parse_price(text: str | None) -> tuple[int | None, bool, str | None]:
    if not text:
        return None, False, None

    text_lower = text.lower()
    if "gratuito" in text_lower or "gratis" in text_lower or "free" in text_lower:
        return None, True, text

    match = _PRICE_PATTERN.search(text)
    if match:
        amount_str = match.group(1)
        amount_str = amount_str.replace(".", "").replace(",", ".")
        amount_cents = round(float(amount_str) * 100)
        notes = "Desde " + text if text.startswith("Desde") else text
        return amount_cents, False, notes

    match = _PRICE_PATTERN_NO_DECIMALS.search(text)
    if match:
        amount_str = match.group(1).replace(".", "")
        amount_cents = int(amount_str) * 100
        notes = "Desde " + text if text.startswith("Desde") else text
        return amount_cents, False, notes

    return None, False, text
