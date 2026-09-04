"""Initial baseline (no tables yet — models arrive in TASK-004+).

Revision ID: 0001_baseline
Revises:
Create Date: 2026-09-04

"""

from collections.abc import Sequence

# revision identifiers, used by Alembic.
revision: str = "0001_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """No-op baseline so upgrade/downgrade plumbing is verified."""
    pass


def downgrade() -> None:
    """No-op baseline rollback."""
    pass
