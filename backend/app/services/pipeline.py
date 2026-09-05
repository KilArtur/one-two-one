"""Оркестрация обработки ответа: транскрибация → анализ → сборка результата.

Цепочка статусов ответа recorded→transcribing→analyzing→ready видна рекрутеру. Сбой
анализа (LLM) не блокирует пайплайн: топик закрывается по имеющимся данным (needs_check),
ответ доводится до ready. По завершении пересобирается InterviewResult кандидата.
"""

from __future__ import annotations

import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.asr import OpenAIWhisperClient, get_asr_client
from app.integrations.llm import LangChainLLMClient, LLMClientError, get_llm_client
from app.integrations.storage import S3StorageClient, get_s3_storage_client
from app.models.answer import Answer, AnswerProcessingStatus
from app.models.question import Question
from app.services.interview_result import assemble_interview_result
from app.services.topic_assessment import assess_topic
from app.services.transcription import _ensure_needs_check, transcribe_answer


async def process_answer(
    session: AsyncSession,
    answer_id: uuid.UUID,
    *,
    asr_client: OpenAIWhisperClient | None = None,
    llm_client: LangChainLLMClient | None = None,
    storage: S3StorageClient | None = None,
) -> Answer | None:
    """Прогоняет ответ по всему пайплайну и пересобирает результат кандидата."""
    asr_client = asr_client or get_asr_client()
    llm_client = llm_client or get_llm_client()
    storage = storage or get_s3_storage_client()

    answer = await transcribe_answer(session, answer_id, asr_client=asr_client, storage=storage)
    if answer is None:
        return None

    # Транскрибация не удалась: 036 уже пометил топик needs_check — просто собираем результат.
    if answer.processing_status == AnswerProcessingStatus.ERROR:
        await _finalize(session, answer.candidate_id)
        return answer

    answer.processing_status = AnswerProcessingStatus.ANALYZING
    await session.commit()

    if answer.candidate_id is not None:
        try:
            await assess_topic(session, answer.candidate_id, answer_id, llm_client=llm_client)
        except LLMClientError:
            # Сбой анализа не блокирует: закрываем топик по имеющимся данным.
            question = await session.get(Question, answer.question_id)
            if question is not None:
                await _ensure_needs_check(session, answer.candidate_id, question.topic_id)
                await session.commit()

    answer.processing_status = AnswerProcessingStatus.READY
    await session.commit()
    await _finalize(session, answer.candidate_id)
    await session.refresh(answer)
    return answer


async def _finalize(session: AsyncSession, candidate_id: uuid.UUID | None) -> None:
    """Пересобирает InterviewResult кандидата, если он известен."""
    if candidate_id is not None:
        await assemble_interview_result(session, candidate_id)
