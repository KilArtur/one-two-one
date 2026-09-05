"""API выпуска, просмотра и отзыва ссылок интервью."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.candidate import Candidate
from app.schemas.interview_link import InterviewLinkRead
from app.services.auth import (
    CurrentUser,
    ensure_interview_link_issue_allowed,
    get_current_user,
)
from app.services.interview_link import (
    get_interview_link,
    issue_interview_link,
    revoke_interview_link,
)
from app.services.question_review import QUESTIONS_NOT_APPROVED, questions_approved

router = APIRouter(tags=["interview-links"])

SessionDep = Annotated[AsyncSession, Depends(get_db)]
CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]

_LINK_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Interview link not found",
)
_CANDIDATE_NOT_FOUND = HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Candidate not found",
)


@router.post(
    "/candidates/{candidate_id}/interview-link",
    response_model=InterviewLinkRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_interview_link(
    candidate_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> InterviewLinkRead:
    """Выпускает новую ссылку интервью кандидату на 7 дней."""
    ensure_interview_link_issue_allowed(current_user)
    candidate = await session.get(Candidate, candidate_id)
    if candidate is None:
        raise _CANDIDATE_NOT_FOUND
    if not await questions_approved(session, candidate.vacancy_id):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=QUESTIONS_NOT_APPROVED)
    link = await issue_interview_link(session, candidate_id)
    if link is None:
        raise _CANDIDATE_NOT_FOUND
    return InterviewLinkRead.model_validate(link)


@router.get("/interview-links/{link_id}", response_model=InterviewLinkRead)
async def read_interview_link(
    link_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> InterviewLinkRead:
    """Возвращает состояние ранее выпущенной ссылки интервью."""
    ensure_interview_link_issue_allowed(current_user)
    link = await get_interview_link(session, link_id)
    if link is None:
        raise _LINK_NOT_FOUND
    return InterviewLinkRead.model_validate(link)


@router.post("/interview-links/{link_id}/revoke", response_model=InterviewLinkRead)
async def revoke_candidate_interview_link(
    link_id: uuid.UUID,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> InterviewLinkRead:
    """Отзывает ссылку интервью."""
    ensure_interview_link_issue_allowed(current_user)
    link = await revoke_interview_link(session, link_id)
    if link is None:
        raise _LINK_NOT_FOUND
    return InterviewLinkRead.model_validate(link)
