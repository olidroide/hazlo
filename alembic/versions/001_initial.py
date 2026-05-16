"""initial migration with JSON columns for value objects

Revision ID: 001_initial
Revises:
Create Date: 2026-05-16

"""
from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("source_type", sa.String(30), nullable=False, server_default=sa.text("'scraper'")),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("fetch_interval_minutes", sa.Integer(), nullable=False, server_default=sa.text("60")),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_status", sa.String(30), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "events",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("location", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("start_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("price", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("ticket_info", sa.dialects.postgresql.JSONB(), nullable=False),
        sa.Column("is_children_activity", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_toddler_friendly", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("source_url", sa.String(1000), nullable=False),
        sa.Column("extracted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'pending'")),
        sa.Column("source_id", sa.UUID(), sa.ForeignKey("sources.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "extraction_runs",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("source_id", sa.UUID(), sa.ForeignKey("sources.id"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'running'")),
        sa.Column("events_found", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("errors", sa.Text(), nullable=True),
    )

    op.create_table(
        "reviews",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("event_id", sa.UUID(), sa.ForeignKey("events.id"), nullable=False),
        sa.Column("reviewer_id", sa.UUID(), nullable=True),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("changes", sa.dialects.postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("reviews")
    op.drop_table("extraction_runs")
    op.drop_table("events")
    op.drop_table("sources")
