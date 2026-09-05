"""Управление ссылками рекрутером и открытие результата внутренними ролями."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Candidate
from app.models.result_link import ResultLink
from app.services.auth import CurrentUser, ensure_interview_link_issue_allowed, get_current_user
from app.services.result_links import issue_result_link, resolve_result_link

router = APIRouter(tags=["result-links"])
SessionDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[CurrentUser, Depends(get_current_user)]


class ResultLinkRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    candidate_id: uuid.UUID
    created_by: str
    expires_at: datetime
    revoked_at: datetime | None


class ResultLinkCreated(ResultLinkRead):
    token: str


class ResolveRequest(BaseModel):
    token: str = Field(min_length=1, max_length=100)


@router.post(
    "/candidates/{candidate_id}/result-links", response_model=ResultLinkCreated, status_code=201
)
async def create_link(
    candidate_id: uuid.UUID, user: UserDep, session: SessionDep
) -> ResultLinkCreated:
    ensure_interview_link_issue_allowed(user)
    link, token = await issue_result_link(session, candidate_id, user)
    return ResultLinkCreated(**ResultLinkRead.model_validate(link).model_dump(), token=token)


@router.get("/candidates/{candidate_id}/result-links", response_model=list[ResultLinkRead])
async def list_links(
    candidate_id: uuid.UUID, user: UserDep, session: SessionDep
) -> list[ResultLink]:
    ensure_interview_link_issue_allowed(user)
    if await session.get(Candidate, candidate_id) is None:
        raise HTTPException(404, "Candidate not found")
    return list(
        await session.scalars(
            select(ResultLink)
            .where(ResultLink.candidate_id == candidate_id)
            .order_by(ResultLink.created_at.desc())
        )
    )


@router.post("/result-links/{link_id}/revoke", response_model=ResultLinkRead)
async def revoke_link(link_id: uuid.UUID, user: UserDep, session: SessionDep) -> ResultLink:
    ensure_interview_link_issue_allowed(user)
    link = await session.scalar(
        select(ResultLink).where(ResultLink.id == link_id).with_for_update()
    )
    if link is None:
        raise HTTPException(404, "Result link not found")
    if link.revoked_at is None:
        link.revoked_at = datetime.now(UTC)
        await session.commit()
        await session.refresh(link)
    return link


@router.post("/result-links/resolve", response_model=ResultLinkRead)
async def resolve(data: ResolveRequest, user: UserDep, session: SessionDep) -> ResultLink:
    return await resolve_result_link(session, data.token)
