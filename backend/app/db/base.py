"""Декларативная база SQLAlchemy — общая метадата для ORM-моделей и Alembic."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Базовый класс всех ORM-моделей проекта."""
