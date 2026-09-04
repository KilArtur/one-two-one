"""Topic ORM model (PRD §5)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, Enum, ForeignKey, Integer, String, Text, true
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import Importance, SkillType

if TYPE_CHECKING:
    from app.models.vacancy import Vacancy


class Topic(Base):
    """Single requirement topic within a vacancy matrix."""

    __tablename__ = "topic"

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
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    skill_type: Mapped[SkillType] = mapped_column(
        Enum(
            SkillType,
            name="skill_type",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    importance: Mapped[Importance] = mapped_column(
        Enum(
            Importance,
            name="importance",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    requirement_description: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="",
    )
    depth_expectations: Mapped[str] = mapped_column(Text, nullable=False, default="")
    verifiable_by_interview: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default=true(),
    )
    order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    vacancy: Mapped[Vacancy] = relationship(back_populates="topics")
