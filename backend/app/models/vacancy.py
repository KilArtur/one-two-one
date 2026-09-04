"""Vacancy ORM model (PRD §5)."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import VacancyGrade, VacancyStatus

if TYPE_CHECKING:
    from app.models.topic import Topic


class Vacancy(Base):
    """Vacancy with versioned requirements matrix."""

    __tablename__ = "vacancy"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    grade: Mapped[VacancyGrade] = mapped_column(
        Enum(
            VacancyGrade,
            name="vacancy_grade",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
    )
    tasks: Mapped[str] = mapped_column(Text, nullable=False, default="")
    stop_factors: Mapped[list[str]] = mapped_column(
        ARRAY(Text),
        nullable=False,
        default=list,
        server_default="{}",
    )
    specialist_profile: Mapped[str] = mapped_column(Text, nullable=False, default="")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[VacancyStatus] = mapped_column(
        Enum(
            VacancyStatus,
            name="vacancy_status",
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
        ),
        nullable=False,
        default=VacancyStatus.DRAFT,
    )

    topics: Mapped[list[Topic]] = relationship(
        back_populates="vacancy",
        cascade="all, delete-orphan",
        order_by="Topic.order",
    )
