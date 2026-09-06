"""ORM-модель внутреннего пользователя (регистрация команды)."""

from __future__ import annotations

import uuid
from enum import StrEnum

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, TimestampMixin, enum_column


class StaffRole(StrEnum):
    """Роль зарегистрированного сотрудника — совпадает с AppRole."""

    RECRUITER = "recruiter"
    TECH_SPECIALIST = "technical_specialist"
    HIRING_MANAGER = "hiring_manager"


class StaffUser(Base, TimestampMixin):
    """Зарегистрированный сотрудник: логин, хеш пароля и роль."""

    __tablename__ = "staff_user"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    username: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[StaffRole] = mapped_column(enum_column(StaffRole, "app_role"), nullable=False)
