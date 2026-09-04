"""ORM-модель вопроса интервью с self-FK для уточнений (раздел 5 PRD)."""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, ForeignKey, Text, Uuid
from sqlalchemy import text as sql_text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_column

if TYPE_CHECKING:
    from app.models.answer import Answer
    from app.models.topic import Topic


class QuestionType(StrEnum):
    """Происхождение вопроса: ядро вакансии, персональный по резюме или уточнение."""

    CORE = "core"
    PERSONAL = "personal"
    FOLLOW_UP = "follow_up"


class QuestionPattern(StrEnum):
    """Паттерн формулировки вопроса."""

    TECHNICAL = "technical"
    EXPERIENCE = "experience"
    REASONING = "reasoning"


class Question(Base, TimestampMixin):
    """Вопрос ровно к одному топику (Р16); уточнения ссылаются на родительский вопрос."""

    __tablename__ = "question"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    topic_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("topic.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[QuestionType] = mapped_column(
        enum_column(QuestionType, "question_type"), nullable=False
    )
    pattern: Mapped[QuestionPattern] = mapped_column(
        enum_column(QuestionPattern, "question_pattern"), nullable=False
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source_reason: Mapped[str | None] = mapped_column(Text)
    reviewed_by_expert: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sql_text("false")
    )
    parent_question_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid, ForeignKey("question.id", ondelete="CASCADE"), index=True
    )

    topic: Mapped[Topic] = relationship(lazy="selectin")
    parent: Mapped[Question | None] = relationship(
        back_populates="follow_ups", remote_side="Question.id"
    )
    follow_ups: Mapped[list[Question]] = relationship(
        back_populates="parent", cascade="all, delete-orphan"
    )
    answers: Mapped[list[Answer]] = relationship(
        back_populates="question",
        cascade="all, delete-orphan",
        order_by="Answer.created_at",
        lazy="selectin",
    )
