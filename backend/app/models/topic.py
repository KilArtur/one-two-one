"""ORM-модель топика требований вакансии (раздел 5 PRD)."""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_column

if TYPE_CHECKING:
    from app.models.vacancy import Vacancy


class SkillType(StrEnum):
    """Тип навыка: определяет, кто ревьюит спорный топик."""

    HARD = "hard"
    SOFT = "soft"


class TopicImportance(StrEnum):
    """Важность требования для решения по кандидату."""

    MANDATORY = "mandatory"
    DESIRED = "desired"


class Topic(Base, TimestampMixin):
    """Требование вакансии, покрытие которого проверяется интервью."""

    __tablename__ = "topic"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    vacancy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("vacancy.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    skill_type: Mapped[SkillType] = mapped_column(
        enum_column(SkillType, "topic_skill_type"), nullable=False
    )
    importance: Mapped[TopicImportance] = mapped_column(
        enum_column(TopicImportance, "topic_importance"), nullable=False
    )
    requirement_description: Mapped[str | None] = mapped_column(Text)
    depth_expectations: Mapped[str | None] = mapped_column(Text)
    verifiable_by_interview: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default=text("0"))

    vacancy: Mapped[Vacancy] = relationship(back_populates="topics")
