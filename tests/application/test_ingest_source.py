from __future__ import annotations

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest

from hazlo.application.use_cases.ingest_source import IngestSource
from hazlo.domain.event import Event, EventStatus, Location, Price, TicketInfo
from hazlo.domain.source import Source, SourceType
from hazlo.infrastructure.adapters.base import BaseSourceAdapter


class FakeAdapter(BaseSourceAdapter):
    def __init__(self, raw_events: list[dict] | None = None, raise_on_fetch: bool = False) -> None:
        self._raw_events = raw_events or []
        self._raise_on_fetch = raise_on_fetch

    async def fetch(self, source_url: str) -> list[dict]:
        if self._raise_on_fetch:
            msg = "Network error"
            raise ConnectionError(msg)
        return self._raw_events

    async def normalize(self, raw: dict) -> Event:
        return Event(
            id=uuid.uuid4(),
            title=raw.get("title", ""),
            location=Location(address=raw.get("address", ""), neighborhood=""),
            start_at=datetime(2026, 6, 1, 20, 0, tzinfo=UTC),
            end_at=datetime(2026, 6, 1, 22, 0, tzinfo=UTC),
            price=Price(amount=Decimal("10"), is_free=False),
            ticket_info=TicketInfo(url=raw.get("ticket_url")),
            source_url=raw.get("source_url", ""),
            extracted_at=datetime.now(UTC),
        )


def _make_source() -> Source:
    return Source(
        name="Test Source",
        source_type=SourceType.SCRAPER,
        url="https://example.com",
    )


def _make_raw_event(url: str = "https://example.com/event/1") -> dict:
    return {
        "title": "Test Event",
        "address": "Calle Mayor 1",
        "ticket_url": "https://tickets.example.com",
        "source_url": url,
    }


@pytest.mark.asyncio
async def test_ingest_creates_pending_events() -> None:
    adapter = FakeAdapter(raw_events=[_make_raw_event(), _make_raw_event("https://example.com/event/2")])
    use_case = IngestSource(adapter_registry={"scraper": adapter})
    source = _make_source()

    result = await use_case.execute(source=source, existing_urls=set())

    assert result.events_found == 2
    assert result.events_new == 2
    assert result.events_skipped == 0
    assert len(result.events_to_save) == 2
    assert all(e.status == EventStatus.PENDING for e in result.events_to_save)
    assert all(e.source_id == source.id for e in result.events_to_save)


@pytest.mark.asyncio
async def test_ingest_skips_duplicate_events() -> None:
    adapter = FakeAdapter(raw_events=[_make_raw_event()])
    use_case = IngestSource(adapter_registry={"scraper": adapter})
    source = _make_source()

    result = await use_case.execute(source=source, existing_urls={"https://example.com/event/1"})

    assert result.events_found == 1
    assert result.events_new == 0
    assert result.events_skipped == 1
    assert len(result.events_to_save) == 0


@pytest.mark.asyncio
async def test_ingest_records_extraction_run() -> None:
    adapter = FakeAdapter(raw_events=[_make_raw_event()])
    use_case = IngestSource(adapter_registry={"scraper": adapter})
    source = _make_source()

    result = await use_case.execute(source=source, existing_urls=set())

    assert result.source_id == source.id
    assert result.started_at is not None
    assert result.finished_at is not None
    assert result.finished_at >= result.started_at


@pytest.mark.asyncio
async def test_ingest_handles_adapter_error_gracefully() -> None:
    adapter = FakeAdapter(raise_on_fetch=True)
    use_case = IngestSource(adapter_registry={"scraper": adapter})
    source = _make_source()

    result = await use_case.execute(source=source, existing_urls=set())

    assert result.events_found == 0
    assert result.events_new == 0
    assert len(result.errors) == 1
    assert "Fetch failed" in result.errors[0]
    assert result.finished_at is not None
