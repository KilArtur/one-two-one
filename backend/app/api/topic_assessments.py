"""API смены статуса топика экспертом с обязательным комментарием (Р21, append-only)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models.topic_assessment import AssessmentStatus
from app.schemas.assessment import TopicAssessmentRead, TopicStatusChangeRequest
from app.services.auth import CurrentUser, get_current_user
from app.services.topic_assessment import change_topic_status

router = APIRouter(prefix="/topic-assessments", tags=["topic-assessments"])

SessionDep = Annotated[AsyncSession, Depends(get_db)]
CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]

_PROFESSIONAL_STATUSES = {
    AssessmentStatus.CONFIRMED,
    AssessmentStatus.NEEDS_CHECK,
    AssessmentStatus.NOT_CONFIRMED,
}


@router.patch("/{assessment_id}/status", response_model=TopicAssessmentRead)
async def change_status(
    assessment_id: uuid.UUID,
    data: TopicStatusChangeRequest,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> TopicAssessmentRead:
    """Меняет current_status топика экспертом; system_status не перезаписывается."""
    if data.new_status not in _PROFESSIONAL_STATUSES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Экспертом выставляется только confirmed/needs_check/not_confirmed",
        )
    assessment = await change_topic_status(
        session,
        assessment_id,
        user=current_user,
        new_status=data.new_status,
        comment=data.comment,
    )
    if assessment is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Topic assessment not found"
        )
    return TopicAssessmentRead.model_validate(assessment)
