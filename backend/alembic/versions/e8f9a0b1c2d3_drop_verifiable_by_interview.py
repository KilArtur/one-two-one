"""drop verifiable by interview

Интервью оценивает только то, что поддаётся оценке; отдельная пометка топика не нужна.

Revision ID: e8f9a0b1c2d3
Revises: d7e8f9a0b1c2
Create Date: 2026-09-05 18:25:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "e8f9a0b1c2d3"
down_revision: str | Sequence[str] | None = "d7e8f9a0b1c2"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Применяет ревизию."""
    op.drop_column("topic", "verifiable_by_interview")


def downgrade() -> None:
    """Откатывает ревизию."""
    op.add_column(
        "topic",
        sa.Column(
            "verifiable_by_interview",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
    )
