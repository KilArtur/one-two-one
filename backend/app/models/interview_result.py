"""ORM-модель детерминированного результата интервью (раздел 5 PRD)."""

from __future__ import annotations

import uuid
from decimal import Decimal
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_column

if TYPE_CHECKING:
    from app.models.candidate import Candidate


class InterviewRecommendation(StrEnum):
    """Детерминированная рекомендация по кандидату."""

    FIT = "fit"
    ADDITIONAL_CHECK = "additional_check"
    NOT_FIT = "not_fit"


class InterviewResult(Base, TimestampMixin):
    """Сводка покрытия и итоговая рекомендация по одному кандидату."""

    __tablename__ = "interview_result"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("candidate.id", ondelete="CASCADE"), primary_key=True
    )
    confirmed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    needs_check_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    not_confirmed_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=text("0")
    )
    mandatory_coverage: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    desired_coverage: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    recommendation: Mapped[InterviewRecommendation] = mapped_column(
        enum_column(InterviewRecommendation, "interview_recommendation"), nullable=False
    )
    vacancy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    model_version: Mapped[str] = mapped_column(String(255), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(255), nullable=False)

    candidate: Mapped[Candidate] = relationship(back_populates="interview_result")
