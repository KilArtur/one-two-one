"""ORM-модель персональной ссылки кандидата на интервью (раздел 5 PRD, Р20)."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.candidate import Candidate


class InterviewLink(Base, TimestampMixin):
    """Одноразовая ссылка: гасится при отправке интервью и отзывается вручную."""

    __tablename__ = "interview_link"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    candidate_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("candidate.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )

    candidate: Mapped[Candidate] = relationship(back_populates="interview_links")
