"""Pydantic-схемы API."""

from app.schemas.vacancy import (
    TopicRead,
    TopicsReplace,
    TopicWrite,
    VacancyCreate,
    VacancyRead,
    VacancyUpdate,
)

__all__ = [
    "TopicRead",
    "TopicWrite",
    "TopicsReplace",
    "VacancyCreate",
    "VacancyRead",
    "VacancyUpdate",
]
