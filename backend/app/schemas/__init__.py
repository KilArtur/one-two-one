"""Pydantic-схемы API."""

from app.schemas.auth import AuthTokenRequest, AuthTokenResponse, CurrentUserRead
from app.schemas.candidate_auth import (
    CandidateSessionExchangeRequest,
    CandidateSessionRead,
    CandidateSessionResponse,
)
from app.schemas.interview_link import CandidateInterviewSubmitResponse, InterviewLinkRead
from app.schemas.question import GeneratedCoreQuestion, QuestionRead
from app.schemas.rbac import RbacCheckResult, TopicStatusChangeCheck
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
    "CandidateSessionExchangeRequest",
    "CandidateSessionRead",
    "CandidateSessionResponse",
    "CandidateInterviewSubmitResponse",
    "CurrentUserRead",
    "GeneratedCoreQuestion",
    "InterviewLinkRead",
    "QuestionRead",
    "RbacCheckResult",
    "TopicStatusChangeCheck",
    "TopicRead",
    "TopicUpdate",
    "TopicWrite",
    "TopicsReplace",
    "VacancyCreate",
    "VacancyRead",
    "VacancyUpdate",
]
