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
from app.integrations.llm import LangChainLLMClient, get_llm_client
from app.integrations.storage import S3StorageError
from app.integrations.tts import TTSClientError
from app.models.candidate import Candidate
from app.models.question import Question, QuestionType
from app.models.topic import Topic
from app.services.consent import require_candidate_consent
from app.services.followup import decide_followup
from app.services.interview_session import mark_current_technically_lost, session_state
from app.services.question_audio import QuestionAudioService, get_question_audio_service

router = APIRouter(prefix="/candidate-interview", tags=["candidate-interview"])
SessionDep = Annotated[AsyncSession, Depends(get_db)]
CandidateDep = Annotated[Candidate, Depends(require_candidate_consent)]


class CandidateQuestionRead(BaseModel):
    """Текст вопроса без внутренних оснований оценки."""

    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    topic_id: uuid.UUID
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


class FollowupRead(BaseModel):
    """Решение об уточняющем вопросе (M4)."""

    ask: bool
    reason: str
    question: CandidateQuestionRead | None = None


@router.post("/topics/{topic_id}/followup", response_model=FollowupRead)
async def request_followup(
    topic_id: uuid.UUID,
    candidate: CandidateDep,
    session: SessionDep,
    llm: Annotated[LangChainLLMClient, Depends(get_llm_client)],
) -> FollowupRead:
    """Решает, нужно ли уточнение по топику, и возвращает follow_up-вопрос (M4/Р12)."""
    topic = await session.scalar(
        select(Topic).where(Topic.id == topic_id, Topic.vacancy_id == candidate.vacancy_id)
    )
    if topic is None:
        raise HTTPException(status_code=404, detail="Topic not found")
    result = await decide_followup(session, candidate.id, topic_id, llm_client=llm)
    question = (
        CandidateQuestionRead.model_validate(result.question) if result.question else None
    )
    return FollowupRead(ask=result.ask, reason=result.reason, question=question)


class SessionStateRead(BaseModel):
    """Состояние сессии для восстановления после обрыва (Р11)."""

    current_question: CandidateQuestionRead | None
    answered_count: int
    total: int
    finished: bool


@router.get("/session", response_model=SessionStateRead)
async def get_session(candidate: CandidateDep, session: SessionDep) -> SessionStateRead:
    """Возвращает текущий вопрос для продолжения (первый неотвеченный)."""
    state = await session_state(session, candidate)
    current = (
        CandidateQuestionRead.model_validate(state.current_question)
        if state.current_question is not None
        else None
    )
    return SessionStateRead(
        current_question=current,
        answered_count=state.answered_count,
        total=state.total,
        finished=state.finished,
    )


@router.post("/session/interrupt", response_model=SessionStateRead)
async def interrupt_session(candidate: CandidateDep, session: SessionDep) -> SessionStateRead:
    """Помечает текущий вопрос technically_lost и возвращает обновлённое состояние."""
    await mark_current_technically_lost(session, candidate)
    state = await session_state(session, candidate)
    current = (
        CandidateQuestionRead.model_validate(state.current_question)
        if state.current_question is not None
        else None
    )
    return SessionStateRead(
        current_question=current,
        answered_count=state.answered_count,
        total=state.total,
        finished=state.finished,
    )
