"""vacancy question examples

Примеры вопросов от техспециалиста — ориентир для генерации ядра.

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3
Create Date: 2026-09-05 18:35:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f9a0b1c2d3e4"
down_revision: str | Sequence[str] | None = "e8f9a0b1c2d3"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Применяет ревизию."""
    op.add_column("vacancy", sa.Column("question_examples", sa.Text(), nullable=True))


def downgrade() -> None:
    """Откатывает ревизию."""
    op.drop_column("vacancy", "question_examples")
