"""Core question generation via LLM with DB cache (M2 / TASK-014)."""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from dataclasses import dataclass, field

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.llm import LLMClient, LLMError, LLMRole
from app.models import Question, QuestionPattern, QuestionType, Topic, Vacancy
from app.prompts import load_prompt
from app.services.vacancy import get_vacancy


class QuestionGenerationError(Exception):
    """LLM or validation failure while generating core questions."""

    def __init__(self, message: str, *, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.cause = cause


class _CoreQuestionDraft(BaseModel):
    """Single core question from structured LLM output."""

    topic_id: uuid.UUID
    pattern: QuestionPattern
    text: str = Field(min_length=1)
    source_reason: str = Field(min_length=1)


class _CoreQuestionsLLMOutput(BaseModel):
    """Native structured output for one vacancy core set."""

    questions: list[_CoreQuestionDraft]


@dataclass(slots=True)
class GenerateCoreResult:
    """Service result: persisted questions plus cache/version metadata."""

    vacancy_id: uuid.UUID
    cached: bool
    questions: list[Question] = field(default_factory=list)
    model_version: str | None = None
    prompt_version: str | None = None


def _interview_topics(vacancy: Vacancy) -> list[Topic]:
    """Topics that participate in the interview (exclude out-of-scope)."""
    topics = [
        t
        for t in vacancy.topics
        if t.verifiable_by_interview
    ]
    return sorted(topics, key=lambda t: (t.order, str(t.id)))


async def _load_core_questions(
    session: AsyncSession,
    topic_ids: Sequence[uuid.UUID],
) -> list[Question]:
    if not topic_ids:
        return []
    result = await session.execute(
        select(Question)
        .where(
            Question.topic_id.in_(list(topic_ids)),
            Question.type == QuestionType.CORE,
        )
        .order_by(Question.topic_id)
    )
    return list(result.scalars().all())


def _build_user_prompt(vacancy: Vacancy, topics: list[Topic]) -> str:
    payload = {
        "vacancy": {
            "title": vacancy.title,
            "grade": vacancy.grade.value,
            "tasks": vacancy.tasks,
            "specialist_profile": vacancy.specialist_profile,
            "version": vacancy.version,
        },
        "topics": [
            {
                "topic_id": str(topic.id),
                "title": topic.title,
                "skill_type": topic.skill_type.value,
                "importance": topic.importance.value,
                "requirement_description": topic.requirement_description,
                "depth_expectations": topic.depth_expectations,
                "order": topic.order,
            }
            for topic in topics
        ],
    }
    return (
        "Generate exactly one core interview question for each topic below.\n"
        "Use the given topic_id values unchanged.\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def _validate_llm_questions(
    drafts: list[_CoreQuestionDraft],
    topics: list[Topic],
) -> None:
    expected = {topic.id for topic in topics}
    got = {draft.topic_id for draft in drafts}
    if got != expected:
        missing = expected - got
        extra = got - expected
        raise QuestionGenerationError(
            f"LLM returned wrong topic set; missing={missing or None}, "
            f"extra={extra or None}",
        )
    if len(drafts) != len(topics):
        raise QuestionGenerationError(
            f"Expected {len(topics)} core questions, got {len(drafts)}",
        )


async def generate_core_questions(
    session: AsyncSession,
    vacancy_id: uuid.UUID,
    *,
    llm: LLMClient | None = None,
) -> GenerateCoreResult | None:
    """Generate or return cached core questions (one per interview topic).

    Cache: if every interview topic already has a ``type=core`` question,
    return them without calling the LLM. On LLM failure the vacancy is left
    unchanged (no partial writes) and ``QuestionGenerationError`` is raised.
    """
    vacancy = await get_vacancy(session, vacancy_id)
    if vacancy is None:
        return None

    topics = _interview_topics(vacancy)
    if not topics:
        return GenerateCoreResult(
            vacancy_id=vacancy.id,
            cached=True,
            questions=[],
        )

    topic_ids = [topic.id for topic in topics]
    existing = await _load_core_questions(session, topic_ids)
    by_topic = {q.topic_id: q for q in existing}

    if all(tid in by_topic for tid in topic_ids):
        cached = [by_topic[tid] for tid in topic_ids]
        return GenerateCoreResult(
            vacancy_id=vacancy.id,
            cached=True,
            questions=cached,
        )

    missing_topics = [t for t in topics if t.id not in by_topic]
    prompt = load_prompt("generate_core_questions")
    client = llm if llm is not None else LLMClient()
    user_prompt = _build_user_prompt(vacancy, missing_topics)

    try:
        result = await client.acomplete_structured(
            user_prompt,
            _CoreQuestionsLLMOutput,
            prompt_version=prompt.version,
            role=LLMRole.QUALITY,
            system=prompt.body,
        )
    except LLMError as exc:
        raise QuestionGenerationError(
            f"Core question generation failed: {exc}",
            cause=exc,
        ) from exc

    drafts = result.content.questions
    _validate_llm_questions(drafts, missing_topics)

    created: list[Question] = []
    for draft in drafts:
        question = Question(
            id=uuid.uuid4(),
            topic_id=draft.topic_id,
            type=QuestionType.CORE,
            pattern=draft.pattern,
            text=draft.text,
            source_reason=draft.source_reason,
            reviewed_by_expert=False,
            parent_question_id=None,
        )
        session.add(question)
        created.append(question)

    try:
        await session.commit()
    except Exception as exc:
        await session.rollback()
        raise QuestionGenerationError(
            f"Failed to persist core questions: {exc}",
            cause=exc,
        ) from exc

    # Re-load all core questions in topic order (cache + newly created).
    all_core = await _load_core_questions(session, topic_ids)
    ordered = {q.topic_id: q for q in all_core}
    return GenerateCoreResult(
        vacancy_id=vacancy.id,
        cached=False,
        model_version=result.model_version,
        prompt_version=result.prompt_version,
        questions=[ordered[tid] for tid in topic_ids if tid in ordered],
    )


async def list_core_questions(
    session: AsyncSession,
    vacancy_id: uuid.UUID,
) -> list[Question] | None:
    """List cached core questions for a vacancy; None if vacancy missing."""
    vacancy = await get_vacancy(session, vacancy_id)
    if vacancy is None:
        return None
    topics = _interview_topics(vacancy)
    if not topics:
        return []
    existing = await _load_core_questions(session, [t.id for t in topics])
    by_topic = {q.topic_id: q for q in existing}
    return [by_topic[t.id] for t in topics if t.id in by_topic]
