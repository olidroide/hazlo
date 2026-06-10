"""add tier column to llm_providers

Allows selecting between free tier (Gemini API) and paid tier (Google Cloud billing).
"""

import sqlalchemy as sa

from alembic import op

revision = "b2c3d4e5f6a7"
down_revision = "a1b2c3d4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "llm_providers",
        sa.Column("tier", sa.String(10), nullable=False, server_default="free"),
    )


def downgrade() -> None:
    op.drop_column("llm_providers", "tier")
