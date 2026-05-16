from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from hazlo.domain.event import Event, EventStatus, Location, Price, TicketInfo
from hazlo.domain.source import Source, SourceType
from hazlo.infrastructure.db.models import Base
from hazlo.infrastructure.db.repositories import EventRepository


@pytest.fixture(scope="session")
def postgres_container() -> PostgresContainer:
    with PostgresContainer("postgres:16-alpine", driver="asyncpg") as postgres:
        yield postgres


@pytest_asyncio.fixture
async def db_session(postgres_container: PostgresContainer) -> AsyncGenerator[AsyncSession, None]:
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
        title="Concierto Jazz",
        location=Location(address="Calle Mayor 1", neighborhood="Centro", metro="Sol"),
        start_at=datetime(2026, 6, 1, 20, 0, tzinfo=UTC),
        end_at=datetime(2026, 6, 1, 22, 0, tzinfo=UTC),
        price=Price(amount=Decimal("15.00"), is_free=False, notes=None),
        ticket_info=TicketInfo(url="https://tickets.example.com", notes=None),
        is_children_activity=False,
        is_toddler_friendly=False,
        source_url="https://source.example.com/event",
        extracted_at=datetime(2026, 5, 16, 10, 0, tzinfo=UTC),
        status=EventStatus.PENDING,
    )


def _make_source() -> Source:
    return Source(
        id=uuid.uuid4(),
        name="Test Source",
        source_type=SourceType.SCRAPER,
        url="https://example.com",
        is_active=True,
        fetch_interval_minutes=30,
    )


@pytest.mark.asyncio
async def test_save_and_get_event(db_session: AsyncSession) -> None:
    repo = EventRepository(db_session)
    event = _make_event()
    saved = await repo.save(event)
    fetched = await repo.get(saved.id)
    assert fetched is not None
    assert fetched.id == saved.id
    assert fetched.title == "Concierto Jazz"
    assert fetched.status == EventStatus.PENDING


@pytest.mark.asyncio
async def test_list_pending_events(db_session: AsyncSession) -> None:
    repo = EventRepository(db_session)
    event1 = _make_event()
    event2 = _make_event()
    event2.title = "Evento Dos"
    approved = _make_event()
    approved.status = EventStatus.APPROVED

    await repo.save(event1)
    await repo.save(event2)
    await repo.save(approved)

    pending = await repo.list_by_status(EventStatus.PENDING)
    assert len(pending) == 2
    assert all(e.status == EventStatus.PENDING for e in pending)


@pytest.mark.asyncio
async def test_update_event_status(db_session: AsyncSession) -> None:
    repo = EventRepository(db_session)
    event = _make_event()
    saved = await repo.save(event)

    updated = await repo.update_status(saved.id, EventStatus.APPROVED)
    assert updated is not None
    assert updated.status == EventStatus.APPROVED

    fetched = await repo.get(saved.id)
    assert fetched is not None
    assert fetched.status == EventStatus.APPROVED
