"""drop extraction_runs.snapshot column

Column created in initial schema but never written or read.
"""

import sqlalchemy as sa

from alembic import op

revision = "a1b2c3d4e5f6"
down_revision = "0f980c683d88"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column("extraction_runs", "snapshot")


def downgrade() -> None:
    op.add_column("extraction_runs", sa.Column("snapshot", sa.JSON(), nullable=True))
