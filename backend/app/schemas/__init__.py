"""Pydantic-схемы API."""

from app.schemas.question import GeneratedCoreQuestion, QuestionRead
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
    "GeneratedCoreQuestion",
    "QuestionRead",
    "TopicRead",
    "TopicUpdate",
    "TopicWrite",
    "TopicsReplace",
    "VacancyCreate",
    "VacancyRead",
    "VacancyUpdate",
]
