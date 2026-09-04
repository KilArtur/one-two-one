"""Add stop_factor_flag table (Р6 / TASK-017).

Revision ID: 0005_stop_factor_flag
Revises: 0004_answer_assessment
Create Date: 2026-09-04

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005_stop_factor_flag"
down_revision: str | None = "0004_answer_assessment"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create stop_factor_flag (1:1 with candidate, separate from topics)."""
    op.create_table(
        "stop_factor_flag",
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "triggered",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "factors",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("reasoning_summary", sa.Text(), nullable=False),
        sa.Column("model_version", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidate.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("candidate_id"),
    )


def downgrade() -> None:
    """Drop stop_factor_flag."""
    op.drop_table("stop_factor_flag")
