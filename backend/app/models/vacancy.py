"""ORM-модель вакансии с версионированием матрицы требований (раздел 5 PRD)."""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import ARRAY, Integer, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, enum_column

if TYPE_CHECKING:
    from app.models.topic import Topic


class VacancyGrade(StrEnum):
    """Грейд вакансии."""

    JUNIOR = "junior"
    MIDDLE = "middle"
    MIDDLE_PLUS = "middle+"
    SENIOR = "senior"


class VacancyStatus(StrEnum):
    """Жизненный цикл вакансии."""

    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class Vacancy(Base, TimestampMixin):
    """Вакансия: грейд, задачи и версия матрицы требований."""

    __tablename__ = "vacancy"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    lineage_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, nullable=False, index=True, default=uuid.uuid4
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    grade: Mapped[VacancyGrade] = mapped_column(
        enum_column(VacancyGrade, "vacancy_grade"), nullable=False
    )
    tasks: Mapped[str | None] = mapped_column(Text)
    specialist_profile: Mapped[str | None] = mapped_column(Text)
    asr_terms: Mapped[list[str]] = mapped_column(
        ARRAY(Text).with_variant(JSON, "sqlite"),
        nullable=False,
        default=list,
        server_default=text("'{}'"),
    )
    version: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default=text("1")
    )
    status: Mapped[VacancyStatus] = mapped_column(
        enum_column(VacancyStatus, "vacancy_status"),
        nullable=False,
        default=VacancyStatus.DRAFT,
        server_default=text("'draft'"),
    )

    topics: Mapped[list[Topic]] = relationship(
        back_populates="vacancy",
        cascade="all, delete-orphan",
        order_by="Topic.order",
        lazy="selectin",
    )
