from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator, Iterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from hazlo.infrastructure.db.models import Base, LLMProviderModel
from hazlo.infrastructure.db.repositories import LLMProviderRepository


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


def _make_provider(*, priority: int, is_active: bool) -> LLMProviderModel:
    return LLMProviderModel(
        id=uuid.uuid4(),
        name=f"Provider-{priority}",
        provider_type="gemini",
        model="gemini-2.0-flash",
        api_key_encrypted="encrypted-key",
        is_active=is_active,
        priority=priority,
    )


@pytest.mark.asyncio
async def test_get_active_returns_none_when_no_active_provider(db_session: AsyncSession) -> None:
    repo = LLMProviderRepository(db_session)
    await repo.save(_make_provider(priority=10, is_active=False))

    active = await repo.get_active()

    assert active is None


@pytest.mark.asyncio
async def test_get_active_returns_lowest_priority_when_multiple_active(db_session: AsyncSession) -> None:
    repo = LLMProviderRepository(db_session)

    high_priority_number = await repo.save(_make_provider(priority=10, is_active=True))
    low_priority_number = await repo.save(_make_provider(priority=1, is_active=True))

    active = await repo.get_active()

    assert active is not None
    assert active.id == low_priority_number.id
    assert active.id != high_priority_number.id
