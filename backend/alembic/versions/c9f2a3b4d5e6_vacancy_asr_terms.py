"""vacancy asr terms

Пользовательский ASR-словарь на вакансию: список технических терминов из матрицы
требований (Kafka, idempotency, ClickHouse и т.д.), TASK-013.

Revision ID: c9f2a3b4d5e6
Revises: b8e1f2c3d4a5
Create Date: 2026-09-04 20:55:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "c9f2a3b4d5e6"
down_revision: str | Sequence[str] | None = "b8e1f2c3d4a5"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Применяет ревизию."""
    op.add_column(
        "vacancy",
        sa.Column(
            "asr_terms",
            sa.ARRAY(sa.Text()).with_variant(sa.JSON(), "sqlite"),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
    )


def downgrade() -> None:
    """Откатывает ревизию."""
    op.drop_column("vacancy", "asr_terms")
