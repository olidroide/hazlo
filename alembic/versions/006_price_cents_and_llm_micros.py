"""migrate price to cents and LLM cost to micros

Revision ID: 006_price_cents_and_llm_micros
Revises: 005_composite_index
Create Date: 2026-05-25

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "006_price_cents_and_llm_micros"
down_revision: str | None = "005_composite_index"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "llm_providers",
        "cost_per_1k_tokens",
        new_column_name="cost_per_1k_tokens_micros",
        existing_type=sa.Float(),
        type_=sa.Integer(),
        postgresql_using="cost_per_1k_tokens::integer",
    )


def downgrade() -> None:
    op.alter_column(
        "llm_providers",
        "cost_per_1k_tokens_micros",
        new_column_name="cost_per_1k_tokens",
        existing_type=sa.Integer(),
        type_=sa.Float(),
        postgresql_using="cost_per_1k_tokens_micros::float",
    )
