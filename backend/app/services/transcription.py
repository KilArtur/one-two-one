"""Транскрибация ответа (M5): статусы recorded→transcribing→ready и детект пустой дорожки.

Async-ядро пайплайна: скачивает аудио из S3, применяет словарь вакансии, пишет
`transcript`/`transcript_segments` и переводит ответ в `ready`. Пустая/подозрительно
короткая дорожка или сбой ASR → `processing_status=error`, а топик получает `needs_check`
(профессиональная оценка не выставляется — «требует проверки» как состояние по умолчанию).
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.asr import ASRClientError, OpenAIWhisperClient, get_asr_client
from app.integrations.storage import S3StorageClient, S3StorageError, get_s3_storage_client
from app.models.answer import Answer, AnswerProcessingStatus
from app.models.question import Question
from app.models.topic import Topic
from app.models.topic_assessment import (
    AssessmentConfidence,
    AssessmentStatus,
    TopicAssessment,
)
from app.models.vacancy import Vacancy

MIN_AUDIO_BYTES = 512
MIN_DURATION_SEC = 1


def _object_key(url: str) -> str:
    """Извлекает ключ объекта из `s3://bucket/key`."""
    return url.split("/", 3)[3]


async def _ensure_needs_check(
    session: AsyncSession, candidate_id: uuid.UUID | None, topic_id: uuid.UUID
) -> None:
    """Ставит топику needs_check при технической ошибке (без проф. оценки)."""
    if candidate_id is None:
        return
    existing = await session.scalar(
        select(TopicAssessment).where(
            TopicAssessment.candidate_id == candidate_id,
            TopicAssessment.topic_id == topic_id,
        )
    )
    if existing is not None:
        return
    session.add(
        TopicAssessment(
            candidate_id=candidate_id,
            topic_id=topic_id,
            system_status=AssessmentStatus.NEEDS_CHECK,
            current_status=AssessmentStatus.NEEDS_CHECK,
            confidence=AssessmentConfidence.LOW,
            signals=None,
            evidence=None,
            reasoning_summary="Техническая ошибка обработки ответа: топик требует проверки.",
        )
    )


async def transcribe_answer(
    session: AsyncSession,
    answer_id: uuid.UUID,
    *,
    asr_client: OpenAIWhisperClient | None = None,
    storage: S3StorageClient | None = None,
) -> Answer | None:
    """Транскрибирует ответ и обновляет его статус (M5)."""
    asr_client = asr_client or get_asr_client()
    storage = storage or get_s3_storage_client()

    answer = await session.get(Answer, answer_id)
    if answer is None:
        return None
    question = await session.get(Question, answer.question_id)
    topic_id = question.topic_id if question is not None else None

    answer.processing_status = AnswerProcessingStatus.TRANSCRIBING
    await session.commit()

    async def fail() -> Answer:
        answer.processing_status = AnswerProcessingStatus.ERROR
        if topic_id is not None:
            await _ensure_needs_check(session, answer.candidate_id, topic_id)
        await session.commit()
        await session.refresh(answer)
        return answer

    if answer.audio_url is None or (
        answer.duration_sec is not None and answer.duration_sec < MIN_DURATION_SEC
    ):
        return await fail()

    try:
        audio = await storage.get_object_bytes(_object_key(answer.audio_url))
    except S3StorageError:
        return await fail()

    if len(audio) < MIN_AUDIO_BYTES:
        return await fail()

    terms: list[str] = []
    if topic_id is not None:
        topic = await session.get(Topic, topic_id)
        if topic is not None:
            vacancy = await session.get(Vacancy, topic.vacancy_id)
            if vacancy is not None:
                terms = list(vacancy.asr_terms)

    try:
        result = await asr_client.transcribe(audio, terms=terms)
    except ASRClientError:
        return await fail()

    if not result.text.strip() or not result.segments:
        return await fail()

    answer.transcript = result.text
    answer.transcript_segments = result.segments
    answer.processing_status = AnswerProcessingStatus.READY
    await session.commit()
    await session.refresh(answer)
    return answer
