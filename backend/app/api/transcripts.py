"""Доступ внутренних ролей к полному транскрипту интервью."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services.auth import CurrentUser, get_current_user
from app.services.transcripts import TranscriptRead, load_transcripts

router = APIRouter(prefix="/candidates", tags=["transcripts"])


@router.get("/{candidate_id}/transcript", response_model=list[TranscriptRead])
async def transcript(
    candidate_id: uuid.UUID,
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    topic_id: uuid.UUID | None = None,
) -> list[TranscriptRead]:
    return await load_transcripts(session, candidate_id, topic_id)
