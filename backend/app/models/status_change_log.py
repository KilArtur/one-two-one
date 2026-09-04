"""StatusChangeLog ORM model (PRD §5) — append-only (insert only)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, Text, event
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import AuthorRole, TopicStatus

if TYPE_CHECKING:
    from app.models.topic_assessment import TopicAssessment


class StatusChangeLog(Base):
    """Append-only audit of topic status changes; updates/deletes are rejected."""

    __tablename__ = "status_change_log"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("topic_assessment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    author_role: Mapped[AuthorRole] = mapped_column(
        Enum(
            AuthorRole,
            name="author_role",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    old_status: Mapped[TopicStatus] = mapped_column(
        Enum(
            TopicStatus,
            name="topic_status",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
            create_constraint=False,
        ),
        nullable=False,
    )
    new_status: Mapped[TopicStatus] = mapped_column(
        Enum(
            TopicStatus,
            name="topic_status",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
            create_constraint=False,
        ),
        nullable=False,
    )
    comment: Mapped[str] = mapped_column(Text, nullable=False, default="")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )

    assessment: Mapped[TopicAssessment] = relationship(back_populates="status_changes")


@event.listens_for(StatusChangeLog, "before_update")
def _reject_status_change_log_update(
    mapper: object,
    connection: object,
    target: StatusChangeLog,
) -> None:
    """Reject in-place edits; history is write-once (insert only)."""
    raise RuntimeError("StatusChangeLog is append-only: updates are not allowed")
