"""add idempotency_key to events

Revision ID: 007_add_idempotency_key
Revises: 006_price_cents_and_llm_micros
Create Date: 2026-05-25
"""
import sqlalchemy as sa

from alembic import op

revision = "007_add_idempotency_key"
down_revision = "006_price_cents_and_llm_micros"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("events", sa.Column("idempotency_key", sa.String(64), nullable=True))
    op.create_unique_constraint("uq_events_idempotency_key", "events", ["idempotency_key"])


def downgrade() -> None:
    op.drop_constraint("uq_events_idempotency_key", "events", type_="unique")
    op.drop_column("events", "idempotency_key")
