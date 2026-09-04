"""ORM-модель ответа кандидата на вопрос интервью (раздел 5 PRD)."""

from __future__ import annotations

import uuid
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, enum_column

if TYPE_CHECKING:
    from app.models.question import Question


class AnswerProcessingStatus(StrEnum):
    """Стадия обработки записанного ответа."""

    RECORDED = "recorded"
    TRANSCRIBING = "transcribing"
    ANALYZING = "analyzing"
    READY = "ready"
    ERROR = "error"


class Answer(Base, TimestampMixin):
    """Ответ кандидата: медиа, транскрипт, таймкоды и статус обработки."""

    __tablename__ = "answer"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("question.id", ondelete="CASCADE"), nullable=False, index=True
    )
    video_url: Mapped[str | None] = mapped_column(String(1024))
    audio_url: Mapped[str | None] = mapped_column(String(1024))
    transcript: Mapped[str | None] = mapped_column(Text)
    transcript_segments: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite")
    )
    duration_sec: Mapped[int | None] = mapped_column(Integer)
    skipped: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    technically_lost: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    processing_status: Mapped[AnswerProcessingStatus] = mapped_column(
        enum_column(AnswerProcessingStatus, "answer_processing_status"),
        nullable=False,
        default=AnswerProcessingStatus.RECORDED,
        server_default=text("'recorded'"),
    )

    question: Mapped[Question] = relationship(back_populates="answers")
