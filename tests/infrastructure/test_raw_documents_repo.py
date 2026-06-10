"""Tests for RawDocumentRepository using Testcontainers PostgreSQL."""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Iterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from hazlo.domain.event import Event, EventStatus, Location, Price, TicketInfo
from hazlo.infrastructure.db.models import Base, event_to_model
from hazlo.infrastructure.db.repositories import RawDocumentRepository


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


def _make_event() -> Event:
    return Event(
        id=uuid.uuid4(),
        title="Test Event",
        location=Location(address="Calle Mayor 1", neighborhood="Centro", metro="Sol"),
        start_at=datetime(2026, 6, 1, 20, 0, tzinfo=UTC),
        end_at=datetime(2026, 6, 1, 22, 0, tzinfo=UTC),
        price=Price(amount_cents=1000, is_free=False, notes=None),
        ticket_info=TicketInfo(url="https://tickets.example.com", notes=None),
        is_children_activity=False,
        is_toddler_friendly=False,
        source_url="https://source.example.com/event",
        extracted_at=datetime(2026, 5, 16, 10, 0, tzinfo=UTC),
        status=EventStatus.PENDING,
    )


async def _persist_event(session: AsyncSession, event: Event) -> Event:
    model = await session.merge(event_to_model(event))
    await session.commit()
    await session.refresh(model)
    from hazlo.infrastructure.db.models import model_to_event

    return model_to_event(model)


@pytest.mark.asyncio
async def test_create_raw_document(db_session: AsyncSession) -> None:
    repo = RawDocumentRepository(db_session)
    event = await _persist_event(db_session, _make_event())

    doc = await repo.create(
        event_id=event.id,
        storage_backend="local",
        storage_uri="/data/raw/test.raw.json",
        content_type="application/rss+xml",
        content_hash="abc123",
        byte_size=1024,
        fetched_at=datetime(2026, 6, 1, 10, 0, tzinfo=UTC),
        source_url="https://example.com/event",
        adapter="rss",
    )
    assert doc.event_id == event.id
    assert doc.status == "pending"
    assert doc.parsed_at is None


@pytest.mark.asyncio
async def test_get_raw_document(db_session: AsyncSession) -> None:
    repo = RawDocumentRepository(db_session)
    event = await _persist_event(db_session, _make_event())

    created = await repo.create(
        event_id=event.id,
        storage_backend="local",
        storage_uri="/data/raw/test.raw.json",
        content_type="application/rss+xml",
        content_hash="abc123",
        byte_size=1024,
        fetched_at=datetime(2026, 6, 1, 10, 0, tzinfo=UTC),
        source_url="https://example.com/event",
        adapter="rss",
    )

    doc = await repo.get(event.id)
    assert doc is not None
    assert doc.id == created.id
    assert doc.event_id == event.id


@pytest.mark.asyncio
async def test_get_raw_document_not_found(db_session: AsyncSession) -> None:
    repo = RawDocumentRepository(db_session)
    doc = await repo.get(uuid.uuid4())
    assert doc is None


@pytest.mark.asyncio
async def test_list_pending_raw_documents(db_session: AsyncSession) -> None:
    repo = RawDocumentRepository(db_session)
    for i in range(3):
        event = _make_event()
        event = event.with_changes(title=f"Test Event {i}", source_url=f"https://source.example.com/event{i}")
        event = await _persist_event(db_session, event)
        await repo.create(
            event_id=event.id,
            storage_backend="local",
            storage_uri=f"/data/raw/test{i}.raw.json",
            content_type="application/rss+xml",
            content_hash=f"hash{i}",
            byte_size=1024,
            fetched_at=datetime(2026, 6, 1, 10, i, tzinfo=UTC),
            source_url=f"https://example.com/event{i}",
            adapter="rss",
        )

    pending = await repo.list_pending(limit=2)
    assert len(pending) == 2


@pytest.mark.asyncio
async def test_mark_parsed(db_session: AsyncSession) -> None:
    repo = RawDocumentRepository(db_session)
    event = await _persist_event(db_session, _make_event())

    doc = await repo.create(
        event_id=event.id,
        storage_backend="local",
        storage_uri="/data/raw/test.raw.json",
        content_type="application/rss+xml",
        content_hash="abc123",
        byte_size=1024,
        fetched_at=datetime(2026, 6, 1, 10, 0, tzinfo=UTC),
        source_url="https://example.com/event",
        adapter="rss",
    )
    assert doc.status == "pending"

    updated = await repo.mark_parsed(doc.id)
    assert updated is not None
    assert updated.status == "parsed"
    assert updated.parsed_at is not None


@pytest.mark.asyncio
async def test_delete_by_event_id(db_session: AsyncSession) -> None:
    repo = RawDocumentRepository(db_session)
    event = await _persist_event(db_session, _make_event())

    await repo.create(
        event_id=event.id,
        storage_backend="local",
        storage_uri="/data/raw/test.raw.json",
        content_type="application/rss+xml",
        content_hash="abc123",
        byte_size=1024,
        fetched_at=datetime(2026, 6, 1, 10, 0, tzinfo=UTC),
        source_url="https://example.com/event",
        adapter="rss",
    )

    deleted = await repo.delete_by_event_id(event.id)
    assert deleted is True

    doc = await repo.get(event.id)
    assert doc is None


@pytest.mark.asyncio
async def test_delete_by_event_id_not_found(db_session: AsyncSession) -> None:
    repo = RawDocumentRepository(db_session)
    deleted = await repo.delete_by_event_id(uuid.uuid4())
    assert deleted is False
