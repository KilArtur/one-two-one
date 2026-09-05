"""drop stop factors

Единственный стоп-фактор — неподтверждённый обязательный топик, отдельная сущность не нужна.

Revision ID: d7e8f9a0b1c2
Revises: c6f7a8b9d0e1
Create Date: 2026-09-05 18:10:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "d7e8f9a0b1c2"
down_revision: str | Sequence[str] | None = "c6f7a8b9d0e1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Применяет ревизию."""
    op.drop_index(op.f("ix_stop_factor_flag_candidate_id"), table_name="stop_factor_flag")
    op.drop_table("stop_factor_flag")
    op.drop_column("vacancy", "stop_factors")


def downgrade() -> None:
    """Откатывает ревизию."""
    op.add_column(
        "vacancy",
        sa.Column(
            "stop_factors",
            postgresql.ARRAY(sa.Text()),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )
    op.create_table(
        "stop_factor_flag",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("stop_factor", sa.Text(), nullable=False),
        sa.Column("triggered", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "confidence",
            postgresql.ENUM(
                "high", "medium", "low", name="assessment_confidence", create_type=False
            ),
            nullable=False,
        ),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reasoning_summary", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_stop_factor_flag_candidate_id"),
        "stop_factor_flag",
        ["candidate_id"],
        unique=False,
    )
