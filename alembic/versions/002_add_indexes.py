"""add indexes for query performance and deduplication

Revision ID: 002_add_indexes
Revises: 001_initial
Create Date: 2026-05-19

"""
from __future__ import annotations

from typing import TYPE_CHECKING

from alembic import op

if TYPE_CHECKING:
    from collections.abc import Sequence

revision: str = "002_add_indexes"
down_revision: str = "001_initial"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("idx_events_status", "events", ["status"])
    op.create_unique_constraint("uq_events_source_url", "events", ["source_url"])
    op.create_index("idx_reviews_event_id", "reviews", ["event_id"])
    op.create_index("idx_extraction_runs_source_id", "extraction_runs", ["source_id"])


def downgrade() -> None:
    op.drop_index("idx_extraction_runs_source_id", table_name="extraction_runs")
    op.drop_index("idx_reviews_event_id", table_name="reviews")
    op.drop_constraint("uq_events_source_url", "events", type_="unique")
    op.drop_index("idx_events_status", table_name="events")
