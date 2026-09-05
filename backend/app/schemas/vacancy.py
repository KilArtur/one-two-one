"""Vacancy and topic API schemas (TASK-011 / TASK-012)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import Importance, SkillType, VacancyGrade, VacancyStatus


def _empty_if_none(value: str | None) -> str:
    return "" if value is None else value


MIN_TOPICS = 1
MAX_TOPICS = 9


def validate_topic_count(count: int, *, allow_empty: bool = False) -> None:
    """Validate topic matrix size: at least 1 (up to 9). Empty allowed only when explicitly opted in."""
    if allow_empty and count == 0:
        return
    if not MIN_TOPICS <= count <= MAX_TOPICS:
        msg = f"Topic count must be {MIN_TOPICS}–{MAX_TOPICS}, got {count}"
        raise ValueError(msg)


class TopicCreate(BaseModel):
    """Topic payload for create/update of a vacancy matrix."""

    title: str = Field(min_length=1, max_length=512)
    skill_type: SkillType
    importance: Importance
    requirement_description: str = ""
    depth_expectations: str = ""
    verifiable_by_interview: bool = True
    order: int = 0

    @field_validator("requirement_description", "depth_expectations", mode="before")
    @classmethod
    def coerce_optional_text(cls, value: object) -> object:
        return _empty_if_none(value if isinstance(value, str) or value is None else str(value))


class TopicUpdate(BaseModel):
    """Partial update of a single topic."""

    title: str | None = Field(default=None, min_length=1, max_length=512)
    skill_type: SkillType | None = None
    importance: Importance | None = None
    requirement_description: str | None = None
    depth_expectations: str | None = None
    verifiable_by_interview: bool | None = None
    order: int | None = None


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

    @field_validator("tasks", "specialist_profile", mode="before")
    @classmethod
    def coerce_optional_text(cls, value: object) -> object:
        return _empty_if_none(value if isinstance(value, str) or value is None else str(value))

    @field_validator("topics")
    @classmethod
    def topics_r8(cls, value: list[TopicCreate]) -> list[TopicCreate]:
        validate_topic_count(len(value), allow_empty=True)
        return value


class VacancyUpdate(BaseModel):
    """Partial update. Omitting `topics` leaves the matrix unchanged."""

    title: str | None = Field(default=None, min_length=1, max_length=512)
    grade: VacancyGrade | None = None
    tasks: str | None = None
    stop_factors: list[str] | None = None
    specialist_profile: str | None = None
    status: VacancyStatus | None = None
    topics: list[TopicCreate] | None = None

    @field_validator("topics")
    @classmethod
    def topics_r8(cls, value: list[TopicCreate] | None) -> list[TopicCreate] | None:
        if value is not None:
            validate_topic_count(len(value), allow_empty=False)
        return value


class VacancyRead(BaseModel):
    """Vacancy with embedded topic matrix."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lineage_id: uuid.UUID
    title: str
    grade: VacancyGrade
    tasks: str = ""
    stop_factors: list[str]
    specialist_profile: str = ""
    version: int
    status: VacancyStatus
    topics: list[TopicRead] = Field(default_factory=list)

    @field_validator("tasks", "specialist_profile", mode="before")
    @classmethod
    def coerce_optional_text(cls, value: object) -> object:
        return _empty_if_none(value if isinstance(value, str) or value is None else str(value))
