"""Shared fixtures for integration tests."""
from __future__ import annotations

from collections.abc import AsyncGenerator, Iterator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from testcontainers.postgres import PostgresContainer

from hazlo.infrastructure.db.models import Base


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    """Start a PostgreSQL container for integration tests."""
    with PostgresContainer("postgres:16-alpine", driver="asyncpg") as postgres:
        yield postgres


@pytest_asyncio.fixture
async def db_session(postgres_container: PostgresContainer) -> AsyncGenerator[AsyncSession]:
    """Create a database session for integration tests."""
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
