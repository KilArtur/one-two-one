"""Сервис выпуска, отзыва и гашения ссылок интервью."""

from __future__ import annotations

import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.candidate import Candidate, CandidateStatus
from app.models.interview_link import InterviewLink

LINK_TTL_DAYS = 7


async def issue_interview_link(
    session: AsyncSession,
    candidate_id: uuid.UUID,
    *,
    now: datetime | None = None,
) -> InterviewLink | None:
    """Выпускает новую ссылку интервью кандидату на 7 дней."""
    candidate = await session.get(Candidate, candidate_id)
    if candidate is None:
        return None

    issued_at = now or datetime.now(UTC)
    link = InterviewLink(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        token=secrets.token_urlsafe(32),
        expires_at=issued_at + timedelta(days=LINK_TTL_DAYS),
        revoked=False,
        used_at=None,
    )
    session.add(link)
    await session.commit()
    await session.refresh(link)
    return link


async def get_interview_link(
    session: AsyncSession,
    link_id: uuid.UUID,
) -> InterviewLink | None:
    """Возвращает ссылку интервью по id."""
    return await session.get(InterviewLink, link_id)


async def revoke_interview_link(
    session: AsyncSession,
    link_id: uuid.UUID,
) -> InterviewLink | None:
    """Отзывает ранее выпущенную ссылку интервью."""
    link = await session.get(InterviewLink, link_id)
    if link is None:
        return None
    link.revoked = True
    await session.commit()
    await session.refresh(link)
    return link


async def submit_candidate_interview(
    session: AsyncSession,
    *,
    candidate_id: uuid.UUID,
    interview_link_id: uuid.UUID,
    now: datetime | None = None,
) -> tuple[Candidate, InterviewLink] | None:
    """Гасит ссылку после отправки интервью и переводит кандидата в submitted."""
    candidate = await session.get(Candidate, candidate_id)
    if candidate is None:
        return None

    submitted_at = now or datetime.now(UTC)
    link = await session.scalar(
        update(InterviewLink)
        .where(
            InterviewLink.id == interview_link_id,
            InterviewLink.candidate_id == candidate_id,
            InterviewLink.revoked.is_(False),
            InterviewLink.used_at.is_(None),
            InterviewLink.expires_at > submitted_at,
        )
        .values(used_at=submitted_at)
        .returning(InterviewLink)
        .execution_options(synchronize_session=False)
    )
    if link is None:
        await session.rollback()
        return None

    candidate.status = CandidateStatus.SUBMITTED
    await session.commit()
    await session.refresh(candidate)
    await session.refresh(link)
    return candidate, link
