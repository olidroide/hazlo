"""Tests for content hash deduplication in EventRepository."""
from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Iterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from hazlo.domain.event import Event, EventStatus, Location, Price, TicketInfo
from hazlo.infrastructure.db.models import Base
from hazlo.infrastructure.db.repositories import EventRepository


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    with PostgresContainer("postgres:16-alpine", driver="asyncpg") as postgres:
        yield postgres


@pytest_asyncio.fixture
async def db_session(postgres_container: PostgresContainer) -> AsyncGenerator[AsyncSession]:
    url = postgres_container.get_connection_url()
    engine = create_async_engine(url, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with session_factory() as session:
        yield session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


def _make_event(content_hash: str | None = "a" * 64) -> Event:
    return Event(
        id=uuid.uuid4(),
        title="Concierto de Jazz",
        location=Location(address="Calle Mayor 1", neighborhood="Centro", metro="Sol"),
        start_at=datetime(2026, 6, 1, 20, 0, tzinfo=UTC),
        end_at=datetime(2026, 6, 1, 22, 0, tzinfo=UTC),
        price=Price(amount_cents=1500, is_free=False, notes=None),
        ticket_info=TicketInfo(url="https://tickets.example.com", notes=None),
        is_children_activity=False,
        is_toddler_friendly=False,
        confidence_score=None,
        agent_review=None,
        source_url=f"https://source.example.com/event/{uuid.uuid4()}",
        extracted_at=datetime(2026, 5, 26, 10, 0, tzinfo=UTC),
        status=EventStatus.PENDING,
        source_id=None,
        idempotency_key=uuid.uuid4().hex,
        content_hash=content_hash,
    )


class TestEventRepositoryContentHash:
    """Test suite for EventRepository content hash methods."""

    @pytest.mark.asyncio
    async def test_exists_by_content_hash_returns_true_when_exists(
        self, db_session: AsyncSession
    ) -> None:
        """Test that exists_by_content_hash returns True when event exists."""
        repo = EventRepository(db_session)
        event = _make_event(content_hash="a" * 64)
        await repo.save(event)
        exists = await repo.exists_by_content_hash(event.content_hash)
        assert exists is True

    @pytest.mark.asyncio
    async def test_exists_by_content_hash_returns_false_when_not_exists(
        self, db_session: AsyncSession
    ) -> None:
        """Test that exists_by_content_hash returns False when event doesn't exist."""
        repo = EventRepository(db_session)
        exists = await repo.exists_by_content_hash("nonexistent_hash")
        assert exists is False

    @pytest.mark.asyncio
    async def test_exists_by_content_hash_returns_false_for_none(
        self, db_session: AsyncSession
    ) -> None:
        """Test that exists_by_content_hash returns False for None hash."""
        repo = EventRepository(db_session)
        exists = await repo.exists_by_content_hash(None)
        assert exists is False

    @pytest.mark.asyncio
    async def test_list_existing_content_hashes_returns_matching_hashes(
        self, db_session: AsyncSession
    ) -> None:
        """Test that list_existing_content_hashes returns hashes that exist."""
        repo = EventRepository(db_session)
        event = _make_event(content_hash="b" * 64)
        await repo.save(event)
        assert event.content_hash is not None
        hashes = {event.content_hash, "nonexistent_hash"}
        existing = await repo.list_existing_content_hashes(hashes)
        assert existing == {event.content_hash}

    @pytest.mark.asyncio
    async def test_list_existing_content_hashes_returns_empty_for_no_matches(
        self, db_session: AsyncSession
    ) -> None:
        """Test that list_existing_content_hashes returns empty set when no matches."""
        repo = EventRepository(db_session)
        hashes = {"hash1", "hash2", "hash3"}
        existing = await repo.list_existing_content_hashes(hashes)
        assert existing == set()

    @pytest.mark.asyncio
    async def test_list_existing_content_handles_empty_input(
        self, db_session: AsyncSession
    ) -> None:
        """Test that list_existing_content_hashes handles empty input."""
        repo = EventRepository(db_session)
        existing = await repo.list_existing_content_hashes(set())
        assert existing == set()
