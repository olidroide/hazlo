"""add composite index for review queue pagination

Revision ID: 005_composite_index
Revises: 004_phase1_llm
Create Date: 2026-05-25

"""
from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "005_composite_index"
down_revision: str | None = "004_phase1_llm"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_index("idx_events_status_created_at", "events", ["status", "created_at"])


def downgrade() -> None:
    op.drop_index("idx_events_status_created_at", table_name="events")
