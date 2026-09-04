"""Vacancy and topic API schemas (TASK-011)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.enums import Importance, SkillType, VacancyGrade, VacancyStatus


class TopicCreate(BaseModel):
    """Topic payload for create/update of a vacancy matrix."""

    title: str = Field(min_length=1, max_length=512)
    skill_type: SkillType
    importance: Importance
    requirement_description: str = ""
    depth_expectations: str = ""
    verifiable_by_interview: bool = True
    order: int = 0


class TopicRead(TopicCreate):
    """Topic as returned from the API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    vacancy_id: uuid.UUID


class VacancyCreate(BaseModel):
    """Create vacancy (optional initial topic matrix)."""

    title: str = Field(min_length=1, max_length=512)
    grade: VacancyGrade
    tasks: str = ""
    stop_factors: list[str] = Field(default_factory=list)
    specialist_profile: str = ""
    status: VacancyStatus = VacancyStatus.DRAFT
    topics: list[TopicCreate] = Field(default_factory=list)


class VacancyUpdate(BaseModel):
    """Partial update. Omitting `topics` leaves the matrix unchanged."""

    title: str | None = Field(default=None, min_length=1, max_length=512)
    grade: VacancyGrade | None = None
    tasks: str | None = None
    stop_factors: list[str] | None = None
    specialist_profile: str | None = None
    status: VacancyStatus | None = None
    topics: list[TopicCreate] | None = None


class VacancyRead(BaseModel):
    """Vacancy with embedded topic matrix."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    grade: VacancyGrade
    tasks: str
    stop_factors: list[str]
    specialist_profile: str
    version: int
    status: VacancyStatus
    topics: list[TopicRead] = Field(default_factory=list)
