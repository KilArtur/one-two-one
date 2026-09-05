"""Схемы вакансии и топиков для CRUD с версионированием матрицы (M1)."""

from __future__ import annotations

import uuid

from pydantic import BaseModel, ConfigDict, Field

from app.models.topic import SkillType, TopicImportance
from app.models.vacancy import VacancyGrade, VacancyStatus


class TopicWrite(BaseModel):
    """Входные данные топика при создании или замене состава требований."""

    title: str = Field(min_length=1, max_length=255)
    skill_type: SkillType
    importance: TopicImportance
    requirement_description: str | None = None
    depth_expectations: str | None = None
    verifiable_by_interview: bool = True
    order: int = 0


class TopicRead(BaseModel):
    """Топик в ответе API."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    title: str
    skill_type: SkillType
    importance: TopicImportance
    requirement_description: str | None
    depth_expectations: str | None
    verifiable_by_interview: bool
    order: int


class TopicUpdate(BaseModel):
    """Частичное редактирование топика (включая пометку «вне зоны интервью», Р15)."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    skill_type: SkillType | None = None
    importance: TopicImportance | None = None
    requirement_description: str | None = None
    depth_expectations: str | None = None
    verifiable_by_interview: bool | None = None
    order: int | None = None


class VacancyCreate(BaseModel):
    """Создание вакансии вместе с исходным составом топиков."""

    title: str = Field(min_length=1, max_length=255)
    grade: VacancyGrade
    tasks: str | None = None
    specialist_profile: str | None = None
    topics: list[TopicWrite] = Field(default_factory=list)


class VacancyUpdate(BaseModel):
    """Частичное обновление скалярных полей вакансии (без изменения состава топиков)."""

    title: str | None = Field(default=None, min_length=1, max_length=255)
    grade: VacancyGrade | None = None
    tasks: str | None = None
    specialist_profile: str | None = None
    status: VacancyStatus | None = None


class TopicsReplace(BaseModel):
    """Новый состав топиков вакансии."""

    topics: list[TopicWrite]


class AsrDictionaryUpdate(BaseModel):
    """Ручное сохранение ASR-словаря вакансии."""

    terms: list[str]


class AsrDictionaryRead(BaseModel):
    """ASR-словарь вакансии: сохранённые термины и авто-подсказки из матрицы."""

    terms: list[str]
    suggested_terms: list[str]


class VacancyRead(BaseModel):
    """Вакансия в ответе API — конкретный снимок версии матрицы."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    lineage_id: uuid.UUID
    title: str
    grade: VacancyGrade
    tasks: str | None
    specialist_profile: str | None
    version: int
    status: VacancyStatus
    topics: list[TopicRead]
