from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Iterator
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from hazlo.domain.event import Event, EventStatus, Location, Price, TicketInfo
from hazlo.domain.review import Review, ReviewAction
from hazlo.infrastructure.db.models import Base
from hazlo.infrastructure.db.repositories import EventRepository, ReviewRepository


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


@pytest.mark.asyncio
async def test_save_review_and_list_by_event(db_session: AsyncSession) -> None:
    event_repo = EventRepository(db_session)
    review_repo = ReviewRepository(db_session)

    event = _make_event()
    saved_event = await event_repo.save(event)

    review = Review(
        event_id=saved_event.id,
        reviewer_id=uuid.uuid4(),
        action=ReviewAction.APPROVE,
        changes={"status": {"before": "pending", "after": "approved"}},
    )
    saved_review = await review_repo.save(review)

    assert saved_review.id is not None
    assert saved_review.action == ReviewAction.APPROVE

    reviews = await review_repo.list_by_event(saved_event.id)
    assert len(reviews) == 1
    assert reviews[0].action == ReviewAction.APPROVE


@pytest.mark.asyncio
async def test_list_reviews_ordered_by_date_desc(db_session: AsyncSession) -> None:
    event_repo = EventRepository(db_session)
    review_repo = ReviewRepository(db_session)

    event = _make_event()
    saved_event = await event_repo.save(event)

    review1 = Review(
        event_id=saved_event.id,
        reviewer_id=uuid.uuid4(),
        action=ReviewAction.APPROVE,
        changes={},
    )
    review2 = Review(
        event_id=saved_event.id,
        reviewer_id=uuid.uuid4(),
        action=ReviewAction.EDIT,
        changes={"title": {"before": "Old", "after": "New"}},
    )
    await review_repo.save(review1)
    await review_repo.save(review2)

    reviews = await review_repo.list_by_event(saved_event.id)
    assert len(reviews) == 2
    assert reviews[0].reviewed_at >= reviews[1].reviewed_at
