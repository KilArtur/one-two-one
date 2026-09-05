"""data deletion log

Append-only лог удаления ПДн кандидата по ретенции/запросу (Р18), TASK-048.

Revision ID: f3c4d5e6a7b8
Revises: e2b3c4d5e6f7
Create Date: 2026-09-05 12:00:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "f3c4d5e6a7b8"
down_revision: str | Sequence[str] | None = "e2b3c4d5e6f7"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Применяет ревизию."""
    op.create_table(
        "data_deletion_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_data_deletion_log_candidate_id"),
        "data_deletion_log",
        ["candidate_id"],
        unique=False,
    )


def downgrade() -> None:
    """Откатывает ревизию."""
    op.drop_index(op.f("ix_data_deletion_log_candidate_id"), table_name="data_deletion_log")
    op.drop_table("data_deletion_log")
