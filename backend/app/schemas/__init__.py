"""Pydantic-схемы API."""

from app.schemas.vacancy import (
    AsrDictionaryRead,
    AsrDictionaryUpdate,
    TopicRead,
    TopicsReplace,
    TopicUpdate,
    TopicWrite,
    VacancyCreate,
    VacancyRead,
    VacancyUpdate,
)

__all__ = [
    "AsrDictionaryRead",
    "AsrDictionaryUpdate",
    "TopicRead",
    "TopicUpdate",
    "TopicWrite",
    "TopicsReplace",
    "VacancyCreate",
    "VacancyRead",
    "VacancyUpdate",
]
