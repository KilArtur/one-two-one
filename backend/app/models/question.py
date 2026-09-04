"""Question ORM model (PRD §5) with self-FK for follow-ups."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, Text, false
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import QuestionPattern, QuestionType

if TYPE_CHECKING:
    from app.models.topic import Topic


class Question(Base):
    """Interview question for one topic; follow-ups via parent_question_id."""

    __tablename__ = "question"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topic.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    type: Mapped[QuestionType] = mapped_column(
        Enum(
            QuestionType,
            name="question_type",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    pattern: Mapped[QuestionPattern] = mapped_column(
        Enum(
            QuestionPattern,
            name="question_pattern",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    source_reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reviewed_by_expert: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    parent_question_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("question.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    topic: Mapped[Topic] = relationship()
    parent: Mapped[Question | None] = relationship(
        remote_side="Question.id",
        back_populates="follow_ups",
    )
    follow_ups: Mapped[list[Question]] = relationship(
        back_populates="parent",
    )
