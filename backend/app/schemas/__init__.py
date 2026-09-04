"""Pydantic-схемы API."""

from app.schemas.auth import AuthTokenRequest, AuthTokenResponse, CurrentUserRead
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
    "AuthTokenRequest",
    "AuthTokenResponse",
    "AsrDictionaryRead",
    "AsrDictionaryUpdate",
    "CurrentUserRead",
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
