"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

# revision identifiers
revision: str = "001_initial"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("source_type", sa.String(30), nullable=False, server_default=sa.text("'web_scraping'")),
        sa.Column("url", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'active'")),
        sa.Column("extraction_frequency_minutes", sa.Integer(), nullable=False, server_default=sa.text("60")),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_success", sa.Boolean(), nullable=True),
        sa.Column("config", sa.dialects.postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "events",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("location_address", sa.String(500), nullable=False),
        sa.Column("location_neighborhood", sa.String(200), nullable=False),
        sa.Column("location_metro_stop", sa.String(200), nullable=True),
        sa.Column("start_time", sa.DateTime(timezone=True), nullable=False),
        sa.Column("end_time", sa.DateTime(timezone=True), nullable=True),
        sa.Column("price_amount", sa.Float(), nullable=True),
        sa.Column("price_is_free", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("price_discount_info", sa.String(500), nullable=True),
        sa.Column("ticket_url", sa.String(1000), nullable=True),
        sa.Column("ticket_point_of_sale", sa.String(500), nullable=True),
        sa.Column("ticket_notes", sa.Text(), nullable=True),
        sa.Column("is_children_activity", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("is_toddler_friendly", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("source_url", sa.String(1000), nullable=True),
        sa.Column("external_id", sa.String(200), nullable=True),
        sa.Column("extraction_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(30), nullable=False, server_default=sa.text("'pending_review'")),
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
        sa.Column("events_created", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("events_updated", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("error_message", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("extraction_runs")
    op.drop_table("events")
    op.drop_table("sources")
