"""Stop-factor flag for a candidate (Р6) — separate from TopicAssessment."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Boolean, ForeignKey, String, Text, false
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.candidate import Candidate


class StopFactorFlag(Base):
    """Per-candidate stop-factor outcome; not mixed into topic assessments."""

    __tablename__ = "stop_factor_flag"

    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidate.id", ondelete="CASCADE"),
        primary_key=True,
    )
    triggered: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=False,
        server_default=false(),
    )
    factors: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
    )
    evidence: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
    )
    reasoning_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    model_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")
    prompt_version: Mapped[str] = mapped_column(String(128), nullable=False, default="")

    candidate: Mapped[Candidate] = relationship()
