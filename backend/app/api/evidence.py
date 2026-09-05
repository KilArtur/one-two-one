"""Evidence и авторизованный доступ к записям с аудитом воспроизведения (Р19)."""

import uuid
from datetime import datetime
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db
from app.integrations.storage import S3StorageClient, S3StorageError, get_s3_storage_client
from app.models.answer import Answer
from app.models.candidate import Candidate
from app.models.question import Question
from app.models.topic_assessment import TopicAssessment
from app.models.video_view import VideoViewLog
from app.services.auth import CurrentUser
from app.services.result_links import get_result_user

router = APIRouter(prefix="/candidates", tags=["evidence"])
SessionDep = Annotated[AsyncSession, Depends(get_db)]
UserDep = Annotated[CurrentUser, Depends(get_result_user)]
StorageDep = Annotated[S3StorageClient, Depends(get_s3_storage_client)]


class EvidenceQuote(BaseModel):
    question_id: uuid.UUID
    quote: str = Field(min_length=1)
    start_sec: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    end_sec: float | None = Field(default=None, ge=0, allow_inf_nan=False)


class EvidenceRead(EvidenceQuote):
    answer_id: uuid.UUID
    question: str
    video_available: bool


async def own_answer(
    session: AsyncSession, candidate_id: uuid.UUID, answer_id: uuid.UUID
) -> Answer:
    answer = await session.scalar(
        select(Answer).where(Answer.id == answer_id, Answer.candidate_id == candidate_id)
    )
    if answer is None:
        raise HTTPException(404, "Answer not found")
    return answer


@router.get("/{candidate_id}/topics/{topic_id}/evidence", response_model=list[EvidenceRead])
async def read_evidence(
    candidate_id: uuid.UUID, topic_id: uuid.UUID, user: UserDep, session: SessionDep
) -> list[EvidenceRead]:
    assessment = await session.scalar(
        select(TopicAssessment).where(
            TopicAssessment.candidate_id == candidate_id, TopicAssessment.topic_id == topic_id
        )
    )
    if assessment is None:
        raise HTTPException(404, "Assessment not found")
    rows = (
        await session.execute(
            select(Answer, Question)
            .join(Question)
            .where(Answer.candidate_id == candidate_id, Question.topic_id == topic_id)
        )
    ).all()
    answers = {question.id: (answer, question) for answer, question in rows}
    evidence = []
    for raw in assessment.evidence or []:
        try:
            quote = EvidenceQuote.model_validate(raw)
        except ValidationError:
            continue
        pair = answers.get(quote.question_id)
        if pair is None:
            continue
        answer, question = pair
        available = bool(answer.video_url and quote.start_sec is not None)
        if quote.start_sec is not None and answer.duration_sec is not None:
            available = available and quote.start_sec < answer.duration_sec
        evidence.append(
            EvidenceRead(
                **quote.model_dump(),
                answer_id=answer.id,
                question=question.text,
                video_available=available,
            )
        )
    return evidence


class MediaRead(BaseModel):
    video_url: str
    audio_url: str | None


async def signed_url(storage: S3StorageClient, url: str) -> str:
    parsed = urlsplit(url)
    if (
        parsed.scheme != "s3"
        or parsed.netloc != get_settings().s3_bucket
        or not parsed.path.lstrip("/")
    ):
        raise HTTPException(404, "Media unavailable")
    return await storage.generate_presigned_get_url(parsed.path.lstrip("/"), expires_in=300)


@router.get("/{candidate_id}/answers/{answer_id}/media", response_model=MediaRead)
async def read_media(
    candidate_id: uuid.UUID,
    answer_id: uuid.UUID,
    user: UserDep,
    session: SessionDep,
    storage: StorageDep,
) -> MediaRead:
    answer = await own_answer(session, candidate_id, answer_id)
    if not answer.video_url:
        raise HTTPException(404, "Media unavailable")
    try:
        return MediaRead(
            video_url=await signed_url(storage, answer.video_url),
            audio_url=await signed_url(storage, answer.audio_url) if answer.audio_url else None,
        )
    except S3StorageError:
        raise HTTPException(503, "Media unavailable") from None


class ViewRequest(BaseModel):
    event_id: uuid.UUID
    position_sec: float = Field(ge=0, allow_inf_nan=False)


class ViewRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    answer_id: uuid.UUID
    viewer: str
    role: str
    position_sec: float
    created_at: datetime


@router.post("/{candidate_id}/answers/{answer_id}/views", response_model=ViewRead)
async def record_view(
    candidate_id: uuid.UUID,
    answer_id: uuid.UUID,
    data: ViewRequest,
    user: UserDep,
    session: SessionDep,
) -> VideoViewLog:
    answer = await own_answer(session, candidate_id, answer_id)
    if not answer.video_url:
        raise HTTPException(404, "Media unavailable")
    if answer.duration_sec is not None and data.position_sec > answer.duration_sec:
        raise HTTPException(422, "Position exceeds recording duration")
    await session.execute(select(Answer.id).where(Answer.id == answer_id).with_for_update())
    existing = await session.get(VideoViewLog, data.event_id)
    if existing:
        if (existing.answer_id, existing.viewer, existing.role) != (
            answer_id,
            user.username,
            user.role.value,
        ):
            raise HTTPException(409, "View identifier already used")
        return existing
    log = VideoViewLog(
        id=data.event_id,
        answer_id=answer_id,
        viewer=user.username,
        role=user.role.value,
        position_sec=data.position_sec,
    )
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


@router.get("/{candidate_id}/video-views", response_model=list[ViewRead])
async def read_views(
    candidate_id: uuid.UUID, user: UserDep, session: SessionDep
) -> list[VideoViewLog]:
    if await session.get(Candidate, candidate_id) is None:
        raise HTTPException(404, "Candidate not found")
    return list(
        await session.scalars(
            select(VideoViewLog)
            .join(Answer)
            .where(Answer.candidate_id == candidate_id)
            .order_by(VideoViewLog.created_at.desc())
        )
    )
