"""Персонализация подтверждённых вопросов под резюме кандидата (M2).

Предмет проверки задаёт техспециалист: персональный вопрос раскрывает тот же топик под
опыт кандидата и не заменяет требование. Сбой модели не блокирует интервью — кандидат
проходит его по подтверждённому ядру.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.integrations.llm import LangChainLLMClient, LLMClientError, get_llm_client
from app.models.candidate import Candidate
from app.models.question import Question, QuestionType
from app.models.topic import Topic
from app.prompts import load_prompt
from app.schemas.question import PersonalizedQuestions

PERSONAL_QUESTION_PROMPT = "personal_question"
PERSONAL_QUESTION_PROMPT_VERSION = "personal-question-v2"
MAX_RESUME_CHARS = 20000


def _format_questions(pairs: list[tuple[Question, Topic]]) -> str:
    return "\n".join(
        f"{index}. {topic.title} — {question.text}"
        for index, (question, topic) in enumerate(pairs, start=1)
    )


async def personalize_questions(
    session: AsyncSession,
    candidate_id: uuid.UUID,
    *,
    llm_client: LangChainLLMClient | None = None,
) -> list[Question]:
    """Создаёт персональные вопросы кандидата из подтверждённого ядра и его резюме."""
    candidate = await session.scalar(
        select(Candidate)
        .where(Candidate.id == candidate_id)
        .options(selectinload(Candidate.vacancy))
    )
    if candidate is None or not (candidate.resume_text or "").strip():
        return []

    existing = await session.scalars(
        select(Question).where(
            Question.candidate_id == candidate_id, Question.type == QuestionType.PERSONAL
        )
    )
    personalized = list(existing)
    if personalized:
        return personalized

    rows = list(
        await session.execute(
            select(Question, Topic)
            .join(Topic, Question.topic_id == Topic.id)
            .where(
                Topic.vacancy_id == candidate.vacancy_id,
                Question.type == QuestionType.CORE,
                Question.reviewed_by_expert.is_(True),
            )
            .order_by(Topic.order, Question.created_at)
        )
    )
    pairs = [(question, topic) for question, topic in rows]
    if not pairs:
        return []

    prompt = load_prompt(PERSONAL_QUESTION_PROMPT).format(
        resume_text=candidate.resume_text[:MAX_RESUME_CHARS],
        questions=_format_questions(pairs),
    )
    llm_client = llm_client or get_llm_client()
    try:
        result = await llm_client.generate_structured(
            prompt,
            schema=PersonalizedQuestions,
            prompt_version=PERSONAL_QUESTION_PROMPT_VERSION,
        )
    except LLMClientError:
        return []

    verdict: PersonalizedQuestions = result.content
    created: list[Question] = []
    for (core, _), item in zip(pairs, verdict.items, strict=False):
        cleaned = item.question.strip()
        # Нет релевантной детали в резюме или модель вернула ядро — оставляем каркас топика.
        if not item.resume_detail.strip() or not cleaned or cleaned == core.text:
            continue
        question = Question(
            candidate_id=candidate_id,
            topic_id=core.topic_id,
            type=QuestionType.PERSONAL,
            pattern=core.pattern,
            text=cleaned,
            source_reason=core.source_reason,
            parent_question_id=core.id,
            reviewed_by_expert=core.reviewed_by_expert,
        )
        session.add(question)
        created.append(question)
    if created:
        await session.commit()
    return created
