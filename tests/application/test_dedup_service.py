from __future__ import annotations

import uuid
from datetime import UTC, datetime

from hazlo.application.services.dedup_service import DedupService
from hazlo.domain.event import Event, Location, Price, TicketInfo


def _make_event(title: str = "Test Event", url: str = "https://example.com/1", date: datetime | None = None) -> Event:
    return Event(
        id=uuid.uuid4(),
        title=title,
        location=Location(address="Calle Mayor 1", neighborhood="Sol"),
        start_at=date or datetime(2026, 6, 1, 20, 0, tzinfo=UTC),
        end_at=datetime(2026, 6, 1, 22, 0, tzinfo=UTC),
        price=Price(is_free=True),
        ticket_info=TicketInfo(),
        source_url=url,
        extracted_at=datetime.now(UTC),
    )


def test_dedup_detects_duplicate_by_url() -> None:
    service = DedupService()
    event = _make_event(url="https://example.com/1")
    existing_urls = {"https://example.com/1"}

    assert service.execute(event, existing_urls) is True


def test_dedup_allows_unique_url() -> None:
    service = DedupService()
    event = _make_event(url="https://example.com/new")
    existing_urls = {"https://example.com/old"}

    assert service.execute(event, existing_urls) is False


def test_dedup_detects_duplicate_by_title_and_date() -> None:
    service = DedupService()
    event = _make_event(title="Test Event", url="https://example.com/new")
    existing_titles = [("Test Event", "2026-06-01")]

    assert service.execute(event, set(), existing_titles) is True


def test_dedup_allows_different_title() -> None:
    service = DedupService()
    event = _make_event(title="Completely Different", url="https://example.com/new")
    existing_titles = [("Test Event", "2026-06-01")]

    assert service.execute(event, set(), existing_titles) is False


def test_dedup_allows_same_title_different_date() -> None:
    service = DedupService()
    event = _make_event(title="Test Event", url="https://example.com/new", date=datetime(2026, 7, 1, 20, 0, tzinfo=UTC))
    existing_titles = [("Test Event", "2026-06-01")]

    assert service.execute(event, set(), existing_titles) is False


def test_dedup_similarity_threshold() -> None:
    service = DedupService()
    event = _make_event(title="Test Event Madrid", url="https://example.com/new")
    existing_titles = [("Test Event Barcelona", "2026-06-01")]

    # Similar but not identical - should be below threshold
    assert service.execute(event, set(), existing_titles) is False


def test_dedup_empty_title() -> None:
    service = DedupService()
    event = _make_event(title="", url="https://example.com/new")
    existing_titles = [("", "2026-06-01")]

    assert service.execute(event, set(), existing_titles) is False
