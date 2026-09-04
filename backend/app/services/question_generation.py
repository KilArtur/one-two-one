"""Генерация ядра вопросов вакансии через LLM (M2).

Один основной вопрос на топик, единый для всех кандидатов (сопоставимость). Результат
кешируется в БД и переиспользуется: повторный вызов не дублирует уже сгенерированные
вопросы. Сбой генерации по топику не блокирует вакансию — топик просто пропускается.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.llm import LangChainLLMClient, LLMClientError, get_llm_client
from app.models.question import Question, QuestionType
from app.models.topic import Topic
from app.models.vacancy import Vacancy
from app.prompts import load_prompt
from app.schemas.question import GeneratedCoreQuestion

CORE_QUESTION_PROMPT = "core_question"
CORE_QUESTION_PROMPT_VERSION = "core-question-v1"


def _format_prompt(vacancy: Vacancy, topic: Topic) -> str:
    """Подставляет контекст вакансии и топика в шаблон промпта."""
    template = load_prompt(CORE_QUESTION_PROMPT)
    return template.format(
        vacancy_title=vacancy.title,
        grade=vacancy.grade.value,
        topic_title=topic.title,
        skill_type=topic.skill_type.value,
        requirement_description=topic.requirement_description or "—",
        depth_expectations=topic.depth_expectations or "—",
    )


async def _existing_core_questions(
    session: AsyncSession, topic_ids: list[uuid.UUID]
) -> dict[uuid.UUID, Question]:
    """Возвращает уже сгенерированные core-вопросы по topic_id (кеш)."""
    if not topic_ids:
        return {}
    rows = await session.scalars(
        select(Question).where(
            Question.topic_id.in_(topic_ids),
            Question.type == QuestionType.CORE,
        )
    )
    existing: dict[uuid.UUID, Question] = {}
    for question in rows:
        existing.setdefault(question.topic_id, question)
    return existing


async def generate_core_questions(
    session: AsyncSession,
    vacancy_id: uuid.UUID,
    *,
    llm_client: LangChainLLMClient | None = None,
) -> list[Question] | None:
    """Генерирует недостающие core-вопросы вакансии и возвращает всё ядро по порядку топиков."""
    llm_client = llm_client or get_llm_client()
    vacancy = await session.get(Vacancy, vacancy_id)
    if vacancy is None:
        return None

    topics = sorted(vacancy.topics, key=lambda item: item.order)
    existing = await _existing_core_questions(session, [topic.id for topic in topics])

    created: list[Question] = []
    for topic in topics:
        if topic.id in existing:
            continue
        try:
            result = await llm_client.generate_structured(
                _format_prompt(vacancy, topic),
                schema=GeneratedCoreQuestion,
                prompt_version=CORE_QUESTION_PROMPT_VERSION,
            )
        except LLMClientError:
            continue

        generated = result.content
        question = Question(
            topic_id=topic.id,
            type=QuestionType.CORE,
            pattern=generated.pattern,
            text=generated.text,
            source_reason=generated.source_reason,
        )
        session.add(question)
        created.append(question)

    if created:
        await session.commit()
        for question in created:
            await session.refresh(question)

    core_by_topic = {**existing, **{question.topic_id: question for question in created}}
    return [core_by_topic[topic.id] for topic in topics if topic.id in core_by_topic]
