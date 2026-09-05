"""Выпуск и проверка ссылок; в БД хранится только хеш случайного секрета."""

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import Depends, Header, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Candidate
from app.models.result_link import ResultLink
from app.services.auth import CurrentUser, get_current_user


async def issue_result_link(
    session: AsyncSession, candidate_id: uuid.UUID, user: CurrentUser
) -> tuple[ResultLink, str]:
    if await session.get(Candidate, candidate_id) is None:
        raise HTTPException(404, "Candidate not found")
    token = secrets.token_urlsafe(32)
    link = ResultLink(
        candidate_id=candidate_id,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        created_by=user.username,
        expires_at=datetime.now(UTC) + timedelta(days=30),
    )
    session.add(link)
    await session.commit()
    await session.refresh(link)
    return link, token


async def resolve_result_link(
    session: AsyncSession, token: str, *, now: datetime | None = None
) -> ResultLink:
    link = await session.scalar(
        select(ResultLink).where(
            ResultLink.token_hash == hashlib.sha256(token.encode()).hexdigest()
        )
    )
    current = now or datetime.now(UTC)
    if link is None or link.revoked_at is not None:
        raise HTTPException(403, "Result link is unavailable")
    expires = (
        link.expires_at.replace(tzinfo=UTC) if link.expires_at.tzinfo is None else link.expires_at
    )
    if expires <= current:
        raise HTTPException(403, "Result link is unavailable")
    return link


async def get_result_user(
    candidate_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    result_link: Annotated[str | None, Header(alias="X-Result-Link")] = None,
) -> CurrentUser:
    if result_link is not None:
        link = await resolve_result_link(session, result_link)
        if link.candidate_id != candidate_id:
            raise HTTPException(403, "Result link is unavailable")
    return user
