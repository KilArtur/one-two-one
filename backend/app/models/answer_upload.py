"""Состояние раздельной чанковой загрузки видео и аудио ответа."""

import uuid
from typing import Any

from sqlalchemy import ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin


class AnswerUpload(Base, TimestampMixin):
    """Манифест загруженных частей; изменения сериализуются блокировкой строки."""

    __tablename__ = "answer_upload"
    __table_args__ = (UniqueConstraint("candidate_id", "question_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("candidate.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("question.id", ondelete="CASCADE"), nullable=False
    )
    manifest: Mapped[dict[str, Any]] = mapped_column(
        JSONB().with_variant(JSON, "sqlite"), nullable=False, default=dict
    )
