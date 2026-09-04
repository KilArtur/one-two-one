"""initial baseline

Базовая ревизия — точка отсчёта цепочки миграций. Таблицы доменной модели
(vacancy, topic и далее) добавляются следующими ревизиями.

Revision ID: 11d73faaed8f
Revises:
Create Date: 2026-09-04 17:55:11.445888
"""

from collections.abc import Sequence

revision: str = "11d73faaed8f"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Применяет ревизию."""


def downgrade() -> None:
    """Откатывает ревизию."""
