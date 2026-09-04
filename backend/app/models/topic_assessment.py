"""TopicAssessment ORM model (PRD §5); system_status is immutable once set."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Enum, ForeignKey, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import Confidence, TopicStatus

if TYPE_CHECKING:
    from app.models.candidate import Candidate
    from app.models.status_change_log import StatusChangeLog
    from app.models.topic import Topic


class TopicAssessment(Base):
    """Per-topic coverage assessment; system_status never overwritten (Р21)."""

    __tablename__ = "topic_assessment"
    __table_args__ = (
        UniqueConstraint(
            "candidate_id",
            "topic_id",
            name="uq_topic_assessment_candidate_topic",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("candidate.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    topic_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topic.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    system_status: Mapped[TopicStatus] = mapped_column(
        Enum(
            TopicStatus,
            name="topic_status",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    current_status: Mapped[TopicStatus] = mapped_column(
        Enum(
            TopicStatus,
            name="topic_status",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
            create_constraint=False,
        ),
        nullable=False,
    )
    confidence: Mapped[Confidence] = mapped_column(
        Enum(
            Confidence,
            name="confidence",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=Confidence.MEDIUM,
    )
    signals: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=dict,
        server_default="{}",
    )
    evidence: Mapped[list[Any]] = mapped_column(
        JSONB,
        nullable=False,
        default=list,
        server_default="[]",
    )
    reasoning_summary: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    reviewer_comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    candidate: Mapped[Candidate] = relationship()
    topic: Mapped[Topic] = relationship()
    status_changes: Mapped[list[StatusChangeLog]] = relationship(
        back_populates="assessment",
        cascade="all, delete-orphan",
    )
