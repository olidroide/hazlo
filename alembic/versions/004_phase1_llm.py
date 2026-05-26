"""Phase 1: Add confidence_score, agent_review, LLM provider table, extraction run columns

Revision ID: 004_phase1_llm
Revises: 003_add_source_config
Create Date: 2026-05-25

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

from alembic import op

revision: str = "004_phase1_llm"
down_revision: str | None = "003_add_source_config"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Add columns to events table
    op.add_column("events", sa.Column("confidence_score", sa.Float(), nullable=True))
    op.add_column("events", sa.Column("agent_review", JSONB(), nullable=True))

    # Add columns to extraction_runs table
    op.add_column(
        "extraction_runs",
        sa.Column("documents_fetched", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "extraction_runs",
        sa.Column("events_extracted", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "extraction_runs",
        sa.Column("events_created", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "extraction_runs",
        sa.Column("events_flagged", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "extraction_runs",
        sa.Column("events_auto_approved", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "extraction_runs",
        sa.Column("events_auto_rejected", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column("extraction_runs", sa.Column("snapshot", JSONB(), nullable=True))

    # Create LLM providers table
    op.create_table(
        "llm_providers",
        sa.Column("id", sa.UUID(), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("provider_type", sa.String(30), nullable=False),
        sa.Column("model", sa.String(100), nullable=False),
        sa.Column("api_key_encrypted", sa.Text(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("priority", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_calls_per_run", sa.Integer(), nullable=False, server_default="100"),
        sa.Column("cost_per_1k_tokens", sa.Float(), nullable=True, server_default="0.0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )


def downgrade() -> None:
    op.drop_table("llm_providers")

    op.drop_column("extraction_runs", "snapshot")
    op.drop_column("extraction_runs", "events_auto_rejected")
    op.drop_column("extraction_runs", "events_auto_approved")
    op.drop_column("extraction_runs", "events_flagged")
    op.drop_column("extraction_runs", "events_created")
    op.drop_column("extraction_runs", "events_extracted")
    op.drop_column("extraction_runs", "documents_fetched")

    op.drop_column("events", "agent_review")
    op.drop_column("events", "confidence_score")
