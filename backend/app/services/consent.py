"""Согласие кандидата и проверка допуска к интервью."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.candidate import Candidate
from app.models.interview_link import InterviewLink
from app.services.auth import CandidateSession, get_candidate_session


async def get_active_candidate(
    candidate_session: Annotated[CandidateSession, Depends(get_candidate_session)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> Candidate:
    """Проверяет актуальность ссылки даже для ранее выданного JWT."""
    candidate = await session.scalar(
        select(Candidate)
        .join(InterviewLink, InterviewLink.candidate_id == Candidate.id)
        .where(
            Candidate.id == candidate_session.candidate_id,
            InterviewLink.id == candidate_session.interview_link_id,
            InterviewLink.revoked.is_(False),
            InterviewLink.used_at.is_(None),
            InterviewLink.expires_at > datetime.now(UTC),
        )
    )
    if candidate is None:
        raise HTTPException(status_code=403, detail="Interview link is invalid")
    return candidate


async def require_candidate_consent(
    candidate: Annotated[Candidate, Depends(get_active_candidate)],
) -> Candidate:
    """Не допускает кандидата к интервью без сохранённого согласия."""
    if candidate.consent_given_at is None:
        raise HTTPException(status_code=403, detail="Consent is required")
    return candidate


async def give_consent(session: AsyncSession, candidate: Candidate) -> datetime:
    """Сохраняет первое время согласия; повторный запрос его не меняет."""
    consent_given_at = await session.scalar(
        update(Candidate)
        .where(Candidate.id == candidate.id)
        .values(consent_given_at=func.coalesce(Candidate.consent_given_at, datetime.now(UTC)))
        .returning(Candidate.consent_given_at)
    )
    assert consent_given_at is not None
    await session.commit()
    return consent_given_at
