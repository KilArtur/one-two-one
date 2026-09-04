"""Обмен magic link кандидата на короткую JWT-сессию."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_db
from app.models.candidate import Candidate
from app.schemas.candidate_auth import (
    CandidateSessionExchangeRequest,
    CandidateSessionRead,
    CandidateSessionResponse,
)
from app.schemas.consent import ConsentRead, ConsentRequest
from app.schemas.interview_link import CandidateInterviewSubmitResponse
from app.services.auth import (
    CandidateSession,
    create_candidate_access_token,
    exchange_interview_link_token,
    get_candidate_session,
)
from app.services.consent import get_active_candidate, give_consent, require_candidate_consent
from app.services.interview_link import submit_candidate_interview

router = APIRouter(prefix="/candidate-auth", tags=["candidate-auth"])

SessionDep = Annotated[AsyncSession, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
CandidateSessionDep = Annotated[CandidateSession, Depends(get_candidate_session)]
_INVALID_LINK = HTTPException(
    status_code=status.HTTP_403_FORBIDDEN,
    detail="Interview link is invalid",
)


@router.post("/exchange", response_model=CandidateSessionResponse)
async def exchange_candidate_link(
    data: CandidateSessionExchangeRequest,
    session: SessionDep,
    settings: SettingsDep,
) -> CandidateSessionResponse:
    """Обменивает token из InterviewLink на short-lived JWT кандидата."""
    candidate_session = await exchange_interview_link_token(
        session,
        data.token,
        settings=settings,
    )
    return CandidateSessionResponse(
        access_token=create_candidate_access_token(
            candidate_id=candidate_session.candidate_id,
            interview_link_id=candidate_session.interview_link_id,
            settings=settings,
        ),
        candidate_id=candidate_session.candidate_id,
    )


@router.get("/me", response_model=CandidateSessionRead)
async def get_candidate_me(candidate_session: CandidateSessionDep) -> CandidateSessionRead:
    """Возвращает кандидата и link id из валидной short-lived JWT-сессии."""
    return CandidateSessionRead(
        candidate_id=candidate_session.candidate_id,
        interview_link_id=candidate_session.interview_link_id,
    )


@router.post(
    "/submit",
    response_model=CandidateInterviewSubmitResponse,
    dependencies=[Depends(require_candidate_consent)],
)
async def submit_interview(
    candidate_session: CandidateSessionDep,
    session: SessionDep,
) -> CandidateInterviewSubmitResponse:
    """Помечает интервью отправленным и гасит текущую ссылку кандидата."""
    result = await submit_candidate_interview(
        session,
        candidate_id=candidate_session.candidate_id,
        interview_link_id=candidate_session.interview_link_id,
    )
    if result is None:
        raise _INVALID_LINK
    candidate, link = result
    assert link.used_at is not None
    return CandidateInterviewSubmitResponse(
        candidate_id=candidate.id,
        interview_link_id=link.id,
        used_at=link.used_at,
        candidate_status=candidate.status,
    )


@router.get("/consent", response_model=ConsentRead)
async def read_consent(
    candidate: Annotated[Candidate, Depends(get_active_candidate)],
) -> ConsentRead:
    """Возвращает сохранённое согласие для действующей ссылки."""
    return ConsentRead(consent_given_at=candidate.consent_given_at)


@router.post("/consent", response_model=ConsentRead)
async def accept_consent(
    data: ConsentRequest,
    candidate: Annotated[Candidate, Depends(get_active_candidate)],
    session: SessionDep,
) -> ConsentRead:
    """Фиксирует явное согласие кандидата перед началом интервью."""
    return ConsentRead(consent_given_at=await give_consent(session, candidate))


@router.get("/equipment-check", response_model=ConsentRead)
async def equipment_check_access(
    candidate: Annotated[Candidate, Depends(require_candidate_consent)],
) -> ConsentRead:
    """Разрешает переход к проверке оборудования после согласия."""
    return ConsentRead(consent_given_at=candidate.consent_given_at)
