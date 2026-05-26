"""add config JSONB column and make url nullable on sources

Revision ID: 003_add_source_config
Revises: 002_add_indexes
Create Date: 2026-05-22

"""
from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "003_add_source_config"
down_revision: str | None = "002_add_indexes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "sources",
        sa.Column("config", sa.dialects.postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'")),
    )
    op.alter_column("sources", "url", existing_type=sa.String(1000), nullable=True)
    op.alter_column(
        "sources",
        "source_type",
        existing_type=sa.String(30),
        existing_server_default=sa.text("'scraper'"),
        server_default=sa.text("'rss'"),
    )


def downgrade() -> None:
    op.alter_column(
        "sources",
        "source_type",
        existing_type=sa.String(30),
        existing_server_default=sa.text("'rss'"),
        server_default=sa.text("'scraper'"),
    )
    op.alter_column("sources", "url", existing_type=sa.String(1000), nullable=False)
    op.drop_column("sources", "config")
