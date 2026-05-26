"""Tests for content hash deduplication in IngestSource use case."""

from __future__ import annotations

import uuid
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from hazlo.application.services import DedupService, EnrichmentService
from hazlo.application.use_cases.ingest_source import IngestSource
from hazlo.domain.event import Event, EventStatus, Location, Price, TicketInfo
from hazlo.domain.source import Source, SourceType


@pytest.fixture
def mock_adapter() -> MagicMock:
    """Mock adapter that returns raw events."""
    adapter = MagicMock()
    adapter.fetch = AsyncMock()
    adapter.normalize = AsyncMock()
    return adapter


@pytest.fixture
def mock_event_repo() -> MagicMock:
    """Mock event repository."""
    repo = MagicMock()
    repo.list_existing_idempotency_keys = AsyncMock(return_value=set())
    repo.exists_by_content_hash = AsyncMock(return_value=False)
    repo.list_existing_content_hashes = AsyncMock(return_value=set())
    repo.save = AsyncMock()
    return repo


@pytest.fixture
def sample_source() -> Source:
    """Sample source for testing."""
    return Source(
        id=uuid.uuid4(),
        name="Test Source",
        source_type=SourceType.RSS,
        url="https://example.com/feed",
        is_active=True,
        fetch_interval_minutes=60,
    )


@pytest.fixture
def sample_raw_event() -> dict[str, object]:
    """Sample raw event dict."""
    return {
        "title": "Concierto de Jazz",
        "description": "Noche de jazz en vivo",
        "location": "Calle Mayor 1, Madrid",
        "start_at": "2026-06-01T20:00:00",
        "end_at": "2026-06-01T22:00:00",
        "price": "15€",
        "ticket_info": "https://tickets.example.com",
        "source_url": "https://source.example.com/event/123",
    }


@pytest.fixture
def sample_event() -> Event:
    """Sample normalized event."""
    return Event(
        id=uuid.uuid4(),
        title="Concierto de Jazz",
        location=Location(address="Calle Mayor 1", neighborhood="Centro", metro="Sol"),
        start_at=datetime(2026, 6, 1, 20, 0),
        end_at=datetime(2026, 6, 1, 22, 0),
        price=Price(amount_cents=1500, is_free=False, notes=None),
        ticket_info=TicketInfo(url="https://tickets.example.com", notes=None),
        is_children_activity=False,
        is_toddler_friendly=False,
        confidence_score=None,
        agent_review=None,
        source_url="https://source.example.com/event/123",
        extracted_at=datetime(2026, 5, 26, 10, 0),
        status=EventStatus.PENDING,
        source_id=None,
        idempotency_key=None,
        content_hash=None,
    )


class TestIngestSourceContentHashDedup:
    """Test suite for IngestSource content hash deduplication."""

    @pytest.mark.asyncio
    async def test_skips_event_with_existing_content_hash(
        self,
        mock_adapter: MagicMock,
        mock_event_repo: MagicMock,
        sample_source: Source,
        sample_raw_event: dict[str, object],
        sample_event: Event,
    ) -> None:
        """Test that events with existing content_hash are skipped before normalization."""
        # Arrange
        mock_adapter.fetch.return_value = [sample_raw_event]
        mock_adapter.normalize.return_value = sample_event
        existing_hash = Event.compute_content_hash(sample_raw_event)
        mock_event_repo.list_existing_content_hashes.return_value = {existing_hash}

        use_case = IngestSource(
            adapter_registry={"rss": mock_adapter},
            enrichment_service=EnrichmentService(),
            dedup_service=DedupService(),
            event_repo=mock_event_repo,
        )

        # Act
        result = await use_case.execute(source=sample_source, existing_urls=set())

        # Assert
        assert result.events_skipped == 1
        assert result.events_new == 0
        mock_adapter.normalize.assert_not_called()

    @pytest.mark.asyncio
    async def test_processes_event_with_new_content_hash(
        self,
        mock_adapter: MagicMock,
        mock_event_repo: MagicMock,
        sample_source: Source,
        sample_raw_event: dict[str, object],
        sample_event: Event,
    ) -> None:
        """Test that events with new content_hash are processed normally."""
        # Arrange
        mock_adapter.fetch.return_value = [sample_raw_event]
        mock_adapter.normalize.return_value = sample_event
        mock_event_repo.list_existing_content_hashes.return_value = set()

        use_case = IngestSource(
            adapter_registry={"rss": mock_adapter},
            enrichment_service=EnrichmentService(),
            dedup_service=DedupService(),
            event_repo=mock_event_repo,
        )

        # Act
        result = await use_case.execute(source=sample_source, existing_urls=set())

        # Assert
        assert result.events_new == 1
        assert result.events_skipped == 0
        mock_adapter.normalize.assert_called_once()

    @pytest.mark.asyncio
    async def test_content_hash_checked_before_normalize(
        self,
        mock_adapter: MagicMock,
        mock_event_repo: MagicMock,
        sample_source: Source,
        sample_raw_event: dict[str, object],
        sample_event: Event,
    ) -> None:
        """Test that content_hash check happens BEFORE normalize (saves CPU)."""
        # Arrange
        mock_adapter.fetch.return_value = [sample_raw_event]
        mock_adapter.normalize.return_value = sample_event
        existing_hash = Event.compute_content_hash(sample_raw_event)
        mock_event_repo.list_existing_content_hashes.return_value = {existing_hash}

        use_case = IngestSource(
            adapter_registry={"rss": mock_adapter},
            enrichment_service=EnrichmentService(),
            dedup_service=DedupService(),
            event_repo=mock_event_repo,
        )

        # Act
        await use_case.execute(source=sample_source, existing_urls=set())

        # Assert - normalize should NOT be called if content_hash exists
        mock_adapter.normalize.assert_not_called()

    @pytest.mark.asyncio
    async def test_multiple_events_mixed_dedup(
        self,
        mock_adapter: MagicMock,
        mock_event_repo: MagicMock,
        sample_source: Source,
    ) -> None:
        """Test dedup with multiple events (some new, some existing)."""
        # Arrange
        raw_events = [
            {"title": "Event 1", "start_at": "2026-06-01T20:00:00", "source_url": "url1"},
            {"title": "Event 2", "start_at": "2026-06-02T20:00:00", "source_url": "url2"},
            {"title": "Event 3", "start_at": "2026-06-03T20:00:00", "source_url": "url3"},
        ]
        mock_adapter.fetch.return_value = raw_events

        # Event 2 already exists - compute its hash
        existing_hash = Event.compute_content_hash(raw_events[1])
        mock_event_repo.list_existing_content_hashes.return_value = {existing_hash}

        # Mock normalize to return events with different hashes
        def normalize_side_effect(raw):
            event = Event(
                id=uuid.uuid4(),
                title=raw["title"],
                location=Location(address="Madrid", neighborhood="Centro"),
                start_at=datetime(2026, 6, 1, 20, 0),
                source_url=raw["source_url"],
                extracted_at=datetime.now(),
                status=EventStatus.PENDING,
            )
            return event

        mock_adapter.normalize.side_effect = normalize_side_effect

        use_case = IngestSource(
            adapter_registry={"rss": mock_adapter},
            enrichment_service=EnrichmentService(),
            dedup_service=DedupService(),
            event_repo=mock_event_repo,
        )

        # Act
        result = await use_case.execute(source=sample_source, existing_urls=set())

        # Assert - should skip 1, process 2
        assert result.events_skipped == 1
        assert result.events_new == 2
