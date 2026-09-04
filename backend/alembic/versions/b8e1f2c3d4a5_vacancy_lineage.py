"""vacancy lineage id

Колонка lineage_id связывает версии одной логической вакансии (M1, версионирование матрицы).

Revision ID: b8e1f2c3d4a5
Revises: 4ae9c5a1f2d0
Create Date: 2026-09-04 20:15:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "b8e1f2c3d4a5"
down_revision: str | Sequence[str] | None = "4ae9c5a1f2d0"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Применяет ревизию."""
    op.add_column("vacancy", sa.Column("lineage_id", sa.Uuid(), nullable=True))
    op.execute("UPDATE vacancy SET lineage_id = id WHERE lineage_id IS NULL")
    op.alter_column("vacancy", "lineage_id", nullable=False)
    op.create_index(op.f("ix_vacancy_lineage_id"), "vacancy", ["lineage_id"], unique=False)


def downgrade() -> None:
    """Откатывает ревизию."""
    op.drop_index(op.f("ix_vacancy_lineage_id"), table_name="vacancy")
    op.drop_column("vacancy", "lineage_id")
