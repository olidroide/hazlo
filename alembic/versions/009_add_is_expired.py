"""add_is_expired_to_events

Revision ID: 009_add_is_expired
Revises: 008_add_raw_text_fields
Create Date: 2026-05-26 20:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "009_add_is_expired"
down_revision: str | None = "008_add_raw_text_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("events", sa.Column("is_expired", sa.Boolean(), nullable=False, server_default="false"))

    # Backfill: mark pending events with end_at or start_at in the past as expired
    op.execute("""
        UPDATE events
        SET is_expired = true
        WHERE status = 'pending'
          AND is_expired = false
          AND (
              (end_at IS NOT NULL AND end_at < NOW())
              OR (end_at IS NULL AND start_at < NOW())
          )
    """)


def downgrade() -> None:
    op.drop_column("events", "is_expired")
