"""Вопросы и потоковая озвучка для кандидата своей вакансии."""

import uuid
from collections.abc import AsyncIterator
from contextlib import aclosing
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.integrations.storage import S3StorageError
from app.integrations.tts import TTSClientError
from app.models.candidate import Candidate
from app.models.question import Question, QuestionType
from app.models.topic import Topic
from app.services.consent import require_candidate_consent
from app.services.question_audio import QuestionAudioService, get_question_audio_service

router = APIRouter(prefix="/candidate-interview", tags=["candidate-interview"])
SessionDep = Annotated[AsyncSession, Depends(get_db)]
CandidateDep = Annotated[Candidate, Depends(require_candidate_consent)]


class CandidateQuestionRead(BaseModel):
    """Текст вопроса без внутренних оснований оценки."""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    type: QuestionType
    text: str


@router.get("/questions", response_model=list[CandidateQuestionRead])
async def list_questions(candidate: CandidateDep, session: SessionDep) -> list[Question]:
    """Возвращает ядро закреплённой за кандидатом версии вакансии."""
    questions = await session.scalars(
        select(Question)
        .join(Topic, Question.topic_id == Topic.id)
        .where(Topic.vacancy_id == candidate.vacancy_id, Question.type == QuestionType.CORE)
        .order_by(Topic.order, Question.created_at, Question.id)
    )
    return list(questions)


@router.get("/questions/{question_id}/audio")
async def question_audio(
    question_id: uuid.UUID,
    candidate: CandidateDep,
    session: SessionDep,
    audio_service: Annotated[QuestionAudioService, Depends(get_question_audio_service)],
) -> StreamingResponse:
    """Отдаёт MP3; проверяет доступ до обращения к TTS/S3."""
    question = await session.scalar(
        select(Question)
        .join(Topic, Question.topic_id == Topic.id)
        .where(
            Question.id == question_id,
            Topic.vacancy_id == candidate.vacancy_id,
            Question.type == QuestionType.CORE,
        )
    )
    if question is None:
        raise HTTPException(status_code=404, detail="Question not found")
    stream = audio_service.stream_audio(question)
    try:
        first = await anext(stream)
    except (TTSClientError, S3StorageError, StopAsyncIteration):
        await stream.aclose()
        raise HTTPException(status_code=503, detail="Question audio is unavailable") from None

    async def body() -> AsyncIterator[bytes]:
        async with aclosing(stream):
            yield first
            async for chunk in stream:
                yield chunk

    return StreamingResponse(body(), media_type="audio/mpeg", headers={"Cache-Control": "no-store"})
