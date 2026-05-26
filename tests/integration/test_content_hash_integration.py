"""Integration tests for content hash deduplication with real database."""

from __future__ import annotations

import uuid
from datetime import datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from hazlo.domain.event import Event, EventStatus, Location, Price, TicketInfo
from hazlo.domain.source import Source, SourceType
from hazlo.infrastructure.db.repositories import EventRepository, SourceRepository


@pytest.fixture
async def test_source(db_session: AsyncSession) -> Source:
    """Create a test source for integration tests."""
    source_repo = SourceRepository(db_session)
    source = Source(
        id=uuid.uuid4(),
        name="Integration Test Source",
        source_type=SourceType.RSS,
        url="https://example.com/feed",
        is_active=True,
        fetch_interval_minutes=60,
    )
    saved = await source_repo.save(source)
    await db_session.commit()
    return saved


@pytest.mark.asyncio
async def test_content_hash_normalization_dedup(db_session: AsyncSession, test_source: Source) -> None:
    """Test that events with normalized content are deduplicated correctly."""
    repo = EventRepository(db_session)

    # Event 1: base event
    event1 = Event(
        id=uuid.uuid4(),
        title="Concierto de Jazz",
        location=Location(address="Calle Mayor 1", neighborhood="Centro", metro="Sol"),
        start_at=datetime(2026, 6, 1, 20, 0),
        end_at=datetime(2026, 6, 1, 22, 0),
        price=Price(amount_cents=1500, is_free=False),
        ticket_info=TicketInfo(url="https://tickets.example.com"),
        source_url=f"https://example.com/event/{uuid.uuid4()}",
        extracted_at=datetime.now(),
        status=EventStatus.PENDING,
        source_id=test_source.id,
        idempotency_key="key1",
        content_hash=Event.compute_content_hash(
            {
                "title": "Concierto de Jazz",
                "location": "Calle Mayor 1",
                "start_at": "2026-06-01T20:00:00",
            }
        ),
    )

    await repo.save(event1)
    await db_session.commit()

    # Event 2: same content with whitespace/case variations
    event2 = Event(
        id=uuid.uuid4(),
        title="  CONCIERTO  DE  JAZZ  ",
        location=Location(address="calle  mayor  1", neighborhood="Centro", metro="Sol"),
        start_at=datetime(2026, 6, 1, 20, 0),
        end_at=datetime(2026, 6, 1, 22, 0),
        price=Price(amount_cents=1500, is_free=False),
        ticket_info=TicketInfo(url="https://tickets.example.com"),
        source_url=f"https://example.com/event/{uuid.uuid4()}",
        extracted_at=datetime.now(),
        status=EventStatus.PENDING,
        source_id=test_source.id,
        idempotency_key="key2",
        content_hash=Event.compute_content_hash(
            {
                "title": "  CONCIERTO  DE  JAZZ  ",
                "location": "calle  mayor  1",
                "start_at": "2026-06-01T20:00:00",
            }
        ),
    )

    # Verify hashes match after normalization
    assert event1.content_hash == event2.content_hash

    # Verify hash exists in DB
    exists = await repo.exists_by_content_hash(event2.content_hash)
    assert exists is True


@pytest.mark.asyncio
async def test_datetime_normalization_dedup(db_session: AsyncSession, test_source: Source) -> None:
    """Test that events with different datetime formats are deduplicated."""
    repo = EventRepository(db_session)

    # Event with standard format
    event1 = Event(
        id=uuid.uuid4(),
        title="Rock Concert",
        location=Location(address="Avenida 1", neighborhood="Norte"),
        start_at=datetime(2026, 7, 1, 21, 0),
        end_at=datetime(2026, 7, 1, 23, 0),
        price=Price(amount_cents=2000, is_free=False),
        ticket_info=TicketInfo(url="https://tickets.example.com"),
        source_url=f"https://example.com/rock/{uuid.uuid4()}",
        extracted_at=datetime.now(),
        status=EventStatus.PENDING,
        source_id=test_source.id,
        idempotency_key="rock1",
        content_hash=Event.compute_content_hash(
            {
                "title": "Rock Concert",
                "location": "Avenida 1",
                "start_at": "2026-07-01T21:00:00",
            }
        ),
    )

    await repo.save(event1)
    await db_session.commit()

    # Event with Z suffix (UTC indicator)
    event2 = Event(
        id=uuid.uuid4(),
        title="Rock Concert",
        location=Location(address="Avenida 1", neighborhood="Norte"),
        start_at=datetime(2026, 7, 1, 21, 0),
        end_at=datetime(2026, 7, 1, 23, 0),
        price=Price(amount_cents=2000, is_free=False),
        ticket_info=TicketInfo(url="https://tickets.example.com"),
        source_url=f"https://example.com/rock/{uuid.uuid4()}",
        extracted_at=datetime.now(),
        status=EventStatus.PENDING,
        source_id=test_source.id,
        idempotency_key="rock2",
        content_hash=Event.compute_content_hash(
            {
                "title": "Rock Concert",
                "location": "Avenida 1",
                "start_at": "2026-07-01T21:00:00Z",
            }
        ),
    )

    # Verify hashes match after datetime normalization
    assert event1.content_hash == event2.content_hash

    # Verify hash exists in DB
    exists = await repo.exists_by_content_hash(event2.content_hash)
    assert exists is True


@pytest.mark.asyncio
async def test_list_existing_content_hashes(db_session: AsyncSession, test_source: Source) -> None:
    """Test that list_existing_content_hashes returns correct hashes."""
    repo = EventRepository(db_session)

    # Create event with known hash
    event = Event(
        id=uuid.uuid4(),
        title="Test Event",
        location=Location(address="Test St", neighborhood="Test"),
        start_at=datetime(2026, 8, 1, 19, 0),
        end_at=datetime(2026, 8, 1, 21, 0),
        price=Price(amount_cents=1000, is_free=False),
        ticket_info=TicketInfo(url="https://tickets.example.com"),
        source_url=f"https://example.com/test/{uuid.uuid4()}",
        extracted_at=datetime.now(),
        status=EventStatus.PENDING,
        source_id=test_source.id,
        idempotency_key="test1",
        content_hash=Event.compute_content_hash(
            {
                "title": "Test Event",
                "location": "Test St",
                "start_at": "2026-08-01T19:00:00",
            }
        ),
    )

    await repo.save(event)
    await db_session.commit()

    # Query for existing hashes
    assert event.content_hash is not None
    hashes_to_check = {event.content_hash, "nonexistent_hash"}
    existing = await repo.list_existing_content_hashes(hashes_to_check)

    assert existing == {event.content_hash}
