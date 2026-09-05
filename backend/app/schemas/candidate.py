"""Схемы карточки кандидата, собираемой из резюме."""

from __future__ import annotations

from pydantic import BaseModel, Field


class ResumeDraft(BaseModel):
    """Разобранное резюме: навыки, опыт и образование короткими пунктами."""

    full_name: str = Field(description="Имя кандидата из резюме, пустая строка если не указано")
    headline: str = Field(description="Текущая роль одной строкой, например «Backend-разработчик»")
    skills: list[str] = Field(description="Технологии и инструменты, по одному пункту на навык")
    experience: list[str] = Field(
        description="Опыт по пунктам: компания, роль, период и суть задач в одну строку"
    )
    education: list[str] = Field(
        description="Образование по пунктам: учебное заведение, специальность, год"
    )


class ResumeCard(BaseModel):
    """Ответ API: разобранная карточка и готовый текст резюме для приглашения."""

    profile: ResumeDraft
    resume_text: str
