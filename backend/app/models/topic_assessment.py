"""ORM-модели оценки топика и append-only аудита статусов (раздел 5 PRD)."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from sqlalchemy import DateTime, ForeignKey, Text, UniqueConstraint, Uuid, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base, TimestampMixin, enum_column

if TYPE_CHECKING:
    from app.models.candidate import Candidate
    from app.models.topic import Topic


class AssessmentStatus(StrEnum):
    """Профессиональный статус покрытия требования."""

    CONFIRMED = "confirmed"
    NEEDS_CHECK = "needs_check"
    NOT_CONFIRMED = "not_confirmed"
    OUT_OF_SCOPE = "out_of_scope"


class AssessmentConfidence(StrEnum):
    """Категориальная уверенность оценки топика."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class ReviewerRole(StrEnum):
    """Роль автора ручной правки статуса."""

    RECRUITER = "recruiter"
    TECH_SPECIALIST = "technical_specialist"
    HIRING_MANAGER = "hiring_manager"


class TopicAssessment(Base, TimestampMixin):
    """Итог по одному топику: исходный статус системы и текущий статус после ревью."""

    __tablename__ = "topic_assessment"
    __table_args__ = (
        UniqueConstraint("candidate_id", "topic_id", name="uq_topic_assessment_candidate_topic"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("candidate.id", ondelete="CASCADE"), nullable=False, index=True
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("topic.id", ondelete="CASCADE"), nullable=False, index=True
    )
    system_status: Mapped[AssessmentStatus] = mapped_column(
        enum_column(AssessmentStatus, "assessment_status"), nullable=False
    )
    current_status: Mapped[AssessmentStatus] = mapped_column(
        enum_column(AssessmentStatus, "assessment_status"), nullable=False
    )
    confidence: Mapped[AssessmentConfidence] = mapped_column(
        enum_column(AssessmentConfidence, "assessment_confidence"), nullable=False
    )
    signals: Mapped[dict[str, Any] | None] = mapped_column(JSONB().with_variant(JSON, "sqlite"))
    evidence: Mapped[list[dict[str, Any]] | None] = mapped_column(
        JSONB().with_variant(JSON, "sqlite")
    )
    reasoning_summary: Mapped[str | None] = mapped_column(Text)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    reviewer_comment: Mapped[str | None] = mapped_column(Text)

    candidate: Mapped[Candidate] = relationship(back_populates="topic_assessments")
    topic: Mapped[Topic] = relationship(lazy="selectin")
    status_changes: Mapped[list[StatusChangeLog]] = relationship(
        back_populates="assessment",
        cascade="all, delete-orphan",
        order_by="StatusChangeLog.created_at",
        lazy="selectin",
    )


class StatusChangeLog(Base):
    """Append-only аудит ручных изменений статусов топика."""

    __tablename__ = "status_change_log"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("topic_assessment.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[uuid.UUID] = mapped_column(Uuid, nullable=False)
    author_role: Mapped[ReviewerRole] = mapped_column(
        enum_column(ReviewerRole, "reviewer_role"), nullable=False
    )
    old_status: Mapped[AssessmentStatus] = mapped_column(
        enum_column(AssessmentStatus, "assessment_status"), nullable=False
    )
    new_status: Mapped[AssessmentStatus] = mapped_column(
        enum_column(AssessmentStatus, "assessment_status"), nullable=False
    )
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    assessment: Mapped[TopicAssessment] = relationship(back_populates="status_changes")
