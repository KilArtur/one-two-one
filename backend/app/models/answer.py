"""Answer ORM model (PRD §5)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text, false
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import ProcessingStatus

if TYPE_CHECKING:
    from app.models.question import Question


class Answer(Base):
    """Candidate answer to one question, with media and transcript."""

    __tablename__ = "answer"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("question.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    video_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    audio_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    transcript: Mapped[str] = mapped_column(Text, nullable=False, default="")
    transcript_segments: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
    )
    duration_sec: Mapped[int | None] = mapped_column(Integer, nullable=True)
    skipped: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    technically_lost: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    processing_status: Mapped[ProcessingStatus] = mapped_column(
        Enum(
            ProcessingStatus,
            name="processing_status",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=ProcessingStatus.RECORDED,
    )

    question: Mapped[Question] = relationship()
