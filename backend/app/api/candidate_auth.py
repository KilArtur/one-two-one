"""Обмен magic link кандидата на короткую JWT-сессию."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.db import get_db
from app.schemas.candidate_auth import (
    CandidateSessionExchangeRequest,
    CandidateSessionRead,
    CandidateSessionResponse,
)
from app.services.auth import (
    CandidateSession,
    create_candidate_access_token,
    exchange_interview_link_token,
    get_candidate_session,
)

router = APIRouter(prefix="/candidate-auth", tags=["candidate-auth"])

SessionDep = Annotated[AsyncSession, Depends(get_db)]
SettingsDep = Annotated[Settings, Depends(get_settings)]
CandidateSessionDep = Annotated[CandidateSession, Depends(get_candidate_session)]


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
