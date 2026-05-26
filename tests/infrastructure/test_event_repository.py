from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Iterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from hazlo.domain.event import Event, EventStatus, Location, Price, TicketInfo
from hazlo.domain.source import Source, SourceType
from hazlo.infrastructure.db.models import Base
from hazlo.infrastructure.db.repositories import EventRepository, SourceRepository


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
    event_id = uuid.uuid4()
    return Event(
        id=event_id,
        title="Concierto Jazz",
        location=Location(address="Calle Mayor 1", neighborhood="Centro", metro="Sol"),
        start_at=datetime(2026, 6, 1, 20, 0, tzinfo=UTC),
        end_at=datetime(2026, 6, 1, 22, 0, tzinfo=UTC),
        price=Price(amount_cents=1500, is_free=False, notes=None),
        ticket_info=TicketInfo(url="https://tickets.example.com", notes=None),
        is_children_activity=False,
        is_toddler_friendly=False,
        source_url=f"https://source.example.com/event/{event_id}",
        extracted_at=datetime(2026, 5, 16, 10, 0, tzinfo=UTC),
        status=EventStatus.PENDING,
    )


def _make_source() -> Source:
    return Source(
        id=uuid.uuid4(),
        name="Test Source",
        source_type=SourceType.RSS,
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


@pytest.mark.asyncio
async def test_save_with_review_updates_existing_event(db_session: AsyncSession) -> None:
    """save_with_review must MERGE (upsert), not INSERT — no IntegrityError."""
    from hazlo.domain.review import Review, ReviewAction

    repo = EventRepository(db_session)
    event = _make_event()
    saved = await repo.save(event)

    updated = _make_event()
    updated.id = saved.id
    updated.title = "Updated Title"
    updated.status = EventStatus.APPROVED

    review = Review(
        event_id=saved.id,
        reviewer_id=uuid.uuid4(),
        action=ReviewAction.APPROVE,
        changes={"title": "Updated Title"},
    )

    result_event, result_review = await repo.save_with_review(updated, review)

    assert result_event.title == "Updated Title"
    assert result_event.status == EventStatus.APPROVED
    assert result_review.action == ReviewAction.APPROVE

    fetched = await repo.get(saved.id)
    assert fetched is not None
    assert fetched.title == "Updated Title"
    assert fetched.status == EventStatus.APPROVED


@pytest.mark.asyncio
async def test_save_with_review_reject_event(db_session: AsyncSession) -> None:
    """Rejecting an existing event must work without IntegrityError."""
    from hazlo.domain.review import Review, ReviewAction

    repo = EventRepository(db_session)
    event = _make_event()
    saved = await repo.save(event)

    updated = _make_event()
    updated.id = saved.id
    updated.status = EventStatus.REJECTED

    review = Review(
        event_id=saved.id,
        reviewer_id=uuid.uuid4(),
        action=ReviewAction.REJECT,
    )

    result_event, _ = await repo.save_with_review(updated, review)
    assert result_event.status == EventStatus.REJECTED

    fetched = await repo.get(saved.id)
    assert fetched is not None
    assert fetched.status == EventStatus.REJECTED


@pytest.mark.asyncio
async def test_source_save_upsert(db_session: AsyncSession) -> None:
    """SourceRepository.save() must MERGE (upsert), not INSERT — no IntegrityError on re-save."""
    repo = SourceRepository(db_session)
    source = _make_source()
    saved = await repo.save(source)

    updated = _make_source()
    updated.id = saved.id
    updated.name = "Updated Source Name"
    updated.is_active = False

    result = await repo.save(updated)

    assert result.name == "Updated Source Name"
    assert result.is_active is False

    fetched = await repo.get(saved.id)
    assert fetched is not None
    assert fetched.name == "Updated Source Name"
    assert fetched.is_active is False


@pytest.mark.asyncio
async def test_list_by_status_excludes_expired_when_requested(db_session: AsyncSession) -> None:
    repo = EventRepository(db_session)
    active = _make_event()
    active.title = "Active Event"
    expired = _make_event()
    expired.title = "Expired Event"
    expired.is_expired = True

    await repo.save(active)
    await repo.save(expired)

    pending_with_expired = await repo.list_by_status(EventStatus.PENDING, include_expired=True)
    assert any(e.title == "Expired Event" for e in pending_with_expired)

    pending_no_expired = await repo.list_by_status(EventStatus.PENDING, include_expired=False)
    assert not any(e.title == "Expired Event" for e in pending_no_expired)
    assert any(e.title == "Active Event" for e in pending_no_expired)


@pytest.mark.asyncio
async def test_list_existing_urls_for_dedup_includes_all_events(db_session: AsyncSession) -> None:
    repo = EventRepository(db_session)
    e1 = _make_event()
    e2 = _make_event()
    e2.is_expired = True
    e2.status = EventStatus.APPROVED

    await repo.save(e1)
    await repo.save(e2)

    urls = await repo.list_existing_urls_for_dedup()
    assert e1.source_url in urls
    assert e2.source_url in urls
