"""InterviewResult ORM model (PRD §5) — coverage + recommendation."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import Recommendation

if TYPE_CHECKING:
    from app.models.candidate import Candidate


class InterviewResult(Base):
    """Final coverage summary for one candidate (1:1 with candidate)."""

    __tablename__ = "interview_result"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidate.id", ondelete="CASCADE"),
        primary_key=True,
    )
    confirmed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    needs_check_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    not_confirmed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    mandatory_coverage: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )
    desired_coverage: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4),
        nullable=True,
    )
    recommendation: Mapped[Recommendation] = mapped_column(
        Enum(
            Recommendation,
            name="recommendation",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    vacancy_version: Mapped[int] = mapped_column(Integer, nullable=False)
    model_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    prompt_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")

    candidate: Mapped[Candidate] = relationship()
