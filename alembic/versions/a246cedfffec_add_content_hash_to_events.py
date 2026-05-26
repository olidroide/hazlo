"""add_content_hash_to_events

Revision ID: a246cedfffec
Revises: 007_add_idempotency_key
Create Date: 2026-05-26 11:39:44.565282

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'a246cedfffec'
down_revision: str | None = '007_add_idempotency_key'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('events', sa.Column('content_hash', sa.String(64), nullable=True))
    op.create_index('idx_events_content_hash', 'events', ['content_hash'], unique=True)


def downgrade() -> None:
    op.drop_index('idx_events_content_hash', table_name='events')
    op.drop_column('events', 'content_hash')
