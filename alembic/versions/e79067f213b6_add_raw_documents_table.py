"""add raw_documents table

Revision ID: e79067f213b6
Revises: b2c3d4e5f6a7
Create Date: 2026-06-02 14:00:00.000000

"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e79067f213b6'
down_revision: str | None = 'b2c3d4e5f6a7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'raw_documents',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('event_id', sa.UUID(), nullable=True),
        sa.Column('storage_backend', sa.String(length=20), nullable=False),
        sa.Column('storage_uri', sa.String(length=1000), nullable=False),
        sa.Column('content_type', sa.String(length=100), nullable=False),
        sa.Column('content_hash', sa.String(length=64), nullable=False),
        sa.Column('byte_size', sa.Integer(), nullable=False),
        sa.Column('fetched_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('source_url', sa.String(length=1000), nullable=False),
        sa.Column('adapter', sa.String(length=30), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('parsed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['event_id'], ['events.id'], ondelete='CASCADE'),
        sa.UniqueConstraint('event_id'),
    )
    op.create_index('ix_raw_documents_fetched_at', 'raw_documents', ['fetched_at'])
    op.create_index('ix_raw_documents_status', 'raw_documents', ['status'])


def downgrade() -> None:
    op.drop_index('ix_raw_documents_status', table_name='raw_documents')
    op.drop_index('ix_raw_documents_fetched_at', table_name='raw_documents')
    op.drop_table('raw_documents')
