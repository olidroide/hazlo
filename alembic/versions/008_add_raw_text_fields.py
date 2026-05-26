"""add_raw_text_fields

Revision ID: 008_add_raw_text_fields
Revises: a246cedfffec
Create Date: 2026-05-26 18:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = '008_add_raw_text_fields'
down_revision: str | None = 'a246cedfffec'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('events', sa.Column('raw_title', sa.String(500), nullable=False, server_default=''))
    op.add_column('events', sa.Column('description', sa.Text(), nullable=False, server_default=''))
    op.add_column('events', sa.Column('raw_description', sa.Text(), nullable=False, server_default=''))


def downgrade() -> None:
    op.drop_column('events', 'raw_description')
    op.drop_column('events', 'description')
    op.drop_column('events', 'raw_title')
