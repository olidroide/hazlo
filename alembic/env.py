"""Generic entry point for Alembic."""

from __future__ import annotations

from alembic import context

from hazlo.infrastructure.db.models import Base
from hazlo.settings import get_settings

target_metadata = Base.metadata


def _get_url() -> str:
    url = get_settings().database_url
    if "asyncpg" in url:
        return url.replace("asyncpg", "psycopg2")
    return url


def run_migrations_offline() -> None:
    url = _get_url()
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    from sqlalchemy import create_engine

    connectable = create_engine(_get_url())
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
