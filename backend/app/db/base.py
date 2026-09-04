"""Декларативная база SQLAlchemy — общая метадата для ORM-моделей и Alembic."""

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Базовый класс всех ORM-моделей проекта."""


class TimestampMixin:
    """Отметки создания и последнего изменения записи."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now()
    )


def enum_column(enum_cls: type[enum.Enum], name: str) -> Enum:
    """Enum-колонка, хранящая значения членов перечисления, а не их имена."""
    return Enum(enum_cls, name=name, values_callable=lambda members: [m.value for m in members])
