"""API очереди ревью спорных топиков по ролям (M7, принцип 5)."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.schemas.assessment import ReviewQueueItem
from app.services.auth import CurrentUser, get_current_user
from app.services.review_queue import review_queue

router = APIRouter(prefix="/review-queue", tags=["review-queue"])

SessionDep = Annotated[AsyncSession, Depends(get_db)]
CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


@router.get("", response_model=list[ReviewQueueItem])
async def get_review_queue(
    current_user: CurrentUserDep, session: SessionDep
) -> list[ReviewQueueItem]:
    """Спорные топики роли (hard→техспец, soft→НМ), самое неопределённое сверху."""
    items = await review_queue(session, current_user)
    return [ReviewQueueItem.model_validate(item) for item in items]
