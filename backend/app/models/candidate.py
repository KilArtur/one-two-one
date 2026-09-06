"""ORM-модель кандидата на вакансию (раздел 5 PRD)."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, String, Text, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, enum_column

if TYPE_CHECKING:
    from app.models.interview_link import InterviewLink
    from app.models.interview_result import InterviewResult
    from app.models.topic_assessment import TopicAssessment
    from app.models.vacancy import Vacancy


class CandidateStatus(StrEnum):
    """Стадия прохождения и обработки интервью кандидата."""

    INVITED = "invited"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    PROCESSED = "processed"
    REVIEWED = "reviewed"


class Candidate(Base, TimestampMixin):
    """Кандидат: резюме, согласие на обработку ПДн и стадия обработки."""

    __tablename__ = "candidate"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    vacancy_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("vacancy.id", ondelete="CASCADE"), nullable=False, index=True
    )
    full_name: Mapped[str | None] = mapped_column(String(255))
    resume_text: Mapped[str | None] = mapped_column(Text)
    resume_file_url: Mapped[str | None] = mapped_column(String(1024))
    consent_given_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[CandidateStatus] = mapped_column(
        enum_column(CandidateStatus, "candidate_status"),
        nullable=False,
        default=CandidateStatus.INVITED,
        server_default=text("'invited'"),
    )

    vacancy: Mapped[Vacancy] = relationship(lazy="selectin")
    interview_links: Mapped[list[InterviewLink]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
        order_by="InterviewLink.created_at",
        lazy="selectin",
    )
    topic_assessments: Mapped[list[TopicAssessment]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
        order_by="TopicAssessment.created_at",
        lazy="selectin",
    )
    interview_result: Mapped[InterviewResult | None] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )
