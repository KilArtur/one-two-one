"""ORM-модель флага стоп-фактора кандидата (Р6), отдельно от оценки топиков."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, ForeignKey, Text, Uuid, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, enum_column
from app.models.topic_assessment import AssessmentConfidence

if TYPE_CHECKING:
    from app.models.candidate import Candidate


class StopFactorFlag(Base, TimestampMixin):
    """Результат проверки одного стоп-фактора по ответу кандидата (Р6)."""

    __tablename__ = "stop_factor_flag"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("candidate.id", ondelete="CASCADE"), nullable=False, index=True
    )
    stop_factor: Mapped[str] = mapped_column(Text, nullable=False)
    triggered: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    confidence: Mapped[AssessmentConfidence] = mapped_column(
        enum_column(AssessmentConfidence, "assessment_confidence"), nullable=False
    )
    evidence: Mapped[dict[str, Any] | None] = mapped_column(JSONB().with_variant(JSON, "sqlite"))
    reasoning_summary: Mapped[str | None] = mapped_column(Text)

    candidate: Mapped[Candidate] = relationship(lazy="selectin")
