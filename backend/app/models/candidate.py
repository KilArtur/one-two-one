"""Candidate ORM model (PRD §5)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import CandidateStatus

if TYPE_CHECKING:
    from app.models.interview_link import InterviewLink
    from app.models.vacancy import Vacancy


class Candidate(Base):
    """Candidate linked to a vacancy, with consent and funnel status."""

    __tablename__ = "candidate"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    vacancy_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vacancy.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    resume_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    resume_file_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    consent_given_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    status: Mapped[CandidateStatus] = mapped_column(
        Enum(
            CandidateStatus,
            name="candidate_status",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=CandidateStatus.INVITED,
    )

    vacancy: Mapped[Vacancy] = relationship()
    interview_links: Mapped[list[InterviewLink]] = relationship(
        back_populates="candidate",
        cascade="all, delete-orphan",
    )
