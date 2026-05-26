from __future__ import annotations

from hazlo.application.services.enrichment_service import EnrichmentService
from hazlo.domain.event import Location, Price, TicketInfo


def _make_raw_event(**kwargs: object) -> dict:
    return {
        "title": "  Test  Event  ",
        "description": "  Some  description  ",
        "start_at": "2026-06-01T20:00:00",
        "end_at": "2026-06-01T22:00:00",
        "price": "10.50€",
        "location": {"address": "Calle Mayor 1, Sol", "neighborhood": "Sol"},
        "ticket_info": {"url": "https://tickets.example.com"},
        **kwargs,
    }


def test_enrichment_normalizes_title() -> None:
    service = EnrichmentService()
    result = service.execute(_make_raw_event(title="  Extra   Spaces  "))
    assert result["title"] == "Extra Spaces"


def test_enrichment_normalizes_description() -> None:
    service = EnrichmentService()
    result = service.execute(_make_raw_event(description="  Multi   line  "))
    assert result["description"] == "Multi line"


def test_enrichment_normalizes_datetime() -> None:
    service = EnrichmentService()
    result = service.execute(_make_raw_event(start_at="2026-06-01T20:00:00"))
    assert result["start_at"] is not None
    assert result["start_at"].tzinfo is not None


def test_enrichment_normalizes_datetime_none() -> None:
    service = EnrichmentService()
    result = service.execute(_make_raw_event(start_at=None))
    assert result["start_at"] is None


def test_enrichment_normalizes_price_with_amount() -> None:
    service = EnrichmentService()
    result = service.execute(_make_raw_event(price="10.50€"))
    price = result["price"]
    assert isinstance(price, Price)
    assert price.amount_cents == 1050
    assert not price.is_free


def test_enrichment_normalizes_price_free() -> None:
    service = EnrichmentService()
    result = service.execute(_make_raw_event(price="Gratis"))
    price = result["price"]
    assert isinstance(price, Price)
    assert price.is_free


def test_enrichment_normalizes_price_none() -> None:
    service = EnrichmentService()
    result = service.execute(_make_raw_event(price=None))
    price = result["price"]
    assert isinstance(price, Price)
    assert price.is_free


def test_enrichment_normalizes_location_dict() -> None:
    service = EnrichmentService()
    result = service.execute(_make_raw_event(location={"address": "Calle Mayor 1, sol"}))
    location = result["location"]
    assert isinstance(location, Location)
    assert location.address == "Calle Mayor 1, sol"
    assert location.metro == "Sol"


def test_enrichment_normalizes_location_string() -> None:
    service = EnrichmentService()
    result = service.execute(_make_raw_event(location="Calle Mayor 1, Chueca"))
    location = result["location"]
    assert isinstance(location, Location)
    assert "Chueca" in location.neighborhood


def test_enrichment_normalizes_ticket_info_dict() -> None:
    service = EnrichmentService()
    result = service.execute(_make_raw_event(ticket_info={"url": "https://example.com"}))
    ticket_info = result["ticket_info"]
    assert isinstance(ticket_info, TicketInfo)
    assert ticket_info.url == "https://example.com"


def test_enrichment_normalizes_ticket_info_string() -> None:
    service = EnrichmentService()
    result = service.execute(_make_raw_event(ticket_info="https://example.com"))
    ticket_info = result["ticket_info"]
    assert isinstance(ticket_info, TicketInfo)
    assert ticket_info.url == "https://example.com"


def test_enrichment_infers_category_workshop() -> None:
    service = EnrichmentService()
    result = service.execute(_make_raw_event(title="Taller de pintura"))
    assert result["category"] == "workshop"


def test_enrichment_infers_category_music() -> None:
    service = EnrichmentService()
    result = service.execute(_make_raw_event(title="Concierto de jazz"))
    assert result["category"] == "music"


def test_enrichment_infers_category_general() -> None:
    service = EnrichmentService()
    result = service.execute(_make_raw_event(title="Random event"))
    assert result["category"] == "general"
