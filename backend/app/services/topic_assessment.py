"""Topic assessment from transcript via LLM (M6 / TASK-016, Р13 + Р16)."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from typing import Any

from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.llm import LLMClient, LLMError, LLMRole
from app.models import (
    Answer,
    Confidence,
    Question,
    Topic,
    TopicAssessment,
    TopicStatus,
)
from app.prompts import load_prompt
from app.services.topic_status import TopicSignals, resolve_topic_status


class TopicAssessmentError(Exception):
    """LLM or validation failure while assessing a topic."""

    def __init__(self, message: str, *, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.cause = cause


class _EvidenceDraft(BaseModel):
    """Single evidence quote from structured LLM output."""

    quote: str = Field(min_length=1)
    timecode_sec: float = Field(ge=0)


class _SignalsDraft(BaseModel):
    """Three assessment signals for one topic."""

    correctness: bool
    example: bool
    personal_contribution: bool


class _TopicAssessmentLLMOutput(BaseModel):
    """Native structured output for one topic assessment."""

    signals: _SignalsDraft
    confidence: Confidence
    no_experience: bool = False
    evidence: list[_EvidenceDraft] = Field(default_factory=list)
    reasoning_summary: str = Field(min_length=1)


@dataclass(slots=True)
class AssessTopicResult:
    """Service result: persisted assessment plus version metadata."""

    assessment: TopicAssessment
    created: bool
    model_version: str | None = None
    prompt_version: str | None = None
    evidence: list[dict[str, Any]] = field(default_factory=list)


def _build_user_prompt(
    *,
    topic: Topic,
    question: Question,
    answer: Answer,
) -> str:
    payload = {
        "topic": {
            "topic_id": str(topic.id),
            "title": topic.title,
            "requirement_description": topic.requirement_description,
            "depth_expectations": topic.depth_expectations,
            "skill_type": topic.skill_type.value,
            "importance": topic.importance.value,
        },
        "question": {
            "question_id": str(question.id),
            "text": question.text,
            "type": question.type.value,
            "pattern": question.pattern.value,
        },
        "answer": {
            "transcript": answer.transcript,
            "transcript_segments": answer.transcript_segments,
            "skipped": answer.skipped,
            "technically_lost": answer.technically_lost,
        },
    }
    return (
        "Assess the candidate answer for THIS topic only.\n"
        "Ignore mentions of technologies outside the topic requirement (R16).\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def _evidence_dicts(
    drafts: list[_EvidenceDraft],
    *,
    question_id: uuid.UUID,
) -> list[dict[str, Any]]:
    return [
        {
            "quote": item.quote,
            "timecode_sec": item.timecode_sec,
            "question_id": str(question_id),
        }
        for item in drafts
    ]


def _signals_dict(signals: TopicSignals) -> dict[str, bool]:
    return {
        "correctness": signals.correctness,
        "example": signals.example,
        "personal_contribution": signals.personal_contribution,
    }


async def _load_existing(
    session: AsyncSession,
    *,
    candidate_id: uuid.UUID,
    topic_id: uuid.UUID,
) -> TopicAssessment | None:
    result = await session.execute(
        select(TopicAssessment).where(
            TopicAssessment.candidate_id == candidate_id,
            TopicAssessment.topic_id == topic_id,
        )
    )
    return result.scalar_one_or_none()


async def assess_topic(
    session: AsyncSession,
    *,
    candidate_id: uuid.UUID,
    topic: Topic,
    question: Question,
    answer: Answer,
    llm: LLMClient | None = None,
) -> AssessTopicResult:
    """Assess one topic from an answer transcript; fix system_status once (Р21).

    Idempotent: if an assessment already exists for (candidate, topic), return it
    without calling the LLM and without changing ``system_status``.
    """
    if question.topic_id != topic.id:
        raise TopicAssessmentError(
            f"Question {question.id} does not belong to topic {topic.id}",
        )

    existing = await _load_existing(
        session,
        candidate_id=candidate_id,
        topic_id=topic.id,
    )
    if existing is not None:
        return AssessTopicResult(
            assessment=existing,
            created=False,
            evidence=list(existing.evidence),
        )

    # Conscious skip → not_confirmed without LLM (Р13).
    if answer.skipped:
        status = resolve_topic_status(
            signals=TopicSignals(
                correctness=False,
                example=False,
                personal_contribution=False,
            ),
            confidence=Confidence.HIGH,
            question_skipped=True,
        )
        assessment = TopicAssessment(
            id=uuid.uuid4(),
            candidate_id=candidate_id,
            topic_id=topic.id,
            system_status=status,
            current_status=status,
            confidence=Confidence.HIGH,
            signals=_signals_dict(
                TopicSignals(
                    correctness=False,
                    example=False,
                    personal_contribution=False,
                )
            ),
            evidence=[],
            reasoning_summary="Question was consciously skipped by the candidate",
        )
        session.add(assessment)
        await session.commit()
        await session.refresh(assessment)
        return AssessTopicResult(
            assessment=assessment,
            created=True,
            evidence=[],
        )

    # Technical loss → needs_check by default (no professional verdict).
    if answer.technically_lost:
        status = TopicStatus.NEEDS_CHECK
        assessment = TopicAssessment(
            id=uuid.uuid4(),
            candidate_id=candidate_id,
            topic_id=topic.id,
            system_status=status,
            current_status=status,
            confidence=Confidence.LOW,
            signals=_signals_dict(
                TopicSignals(
                    correctness=False,
                    example=False,
                    personal_contribution=False,
                )
            ),
            evidence=[],
            reasoning_summary="Answer technically lost; professional status deferred",
        )
        session.add(assessment)
        await session.commit()
        await session.refresh(assessment)
        return AssessTopicResult(
            assessment=assessment,
            created=True,
            evidence=[],
        )

    prompt = load_prompt("assess_topic")
    client = llm if llm is not None else LLMClient()
    user_prompt = _build_user_prompt(topic=topic, question=question, answer=answer)

    try:
        result = await client.acomplete_structured(
            user_prompt,
            _TopicAssessmentLLMOutput,
            prompt_version=prompt.version,
            role=LLMRole.QUALITY,
            system=prompt.body,
        )
    except LLMError as exc:
        raise TopicAssessmentError(
            f"Topic assessment LLM call failed: {exc}",
            cause=exc,
        ) from exc

    draft = result.content
    signals = TopicSignals(
        correctness=draft.signals.correctness,
        example=draft.signals.example,
        personal_contribution=draft.signals.personal_contribution,
    )
    status = resolve_topic_status(
        signals=signals,
        confidence=draft.confidence,
        no_experience=draft.no_experience,
        question_skipped=False,
    )
    evidence = _evidence_dicts(draft.evidence, question_id=question.id)

    assessment = TopicAssessment(
        id=uuid.uuid4(),
        candidate_id=candidate_id,
        topic_id=topic.id,
        system_status=status,
        current_status=status,
        confidence=draft.confidence,
        signals=_signals_dict(signals),
        evidence=evidence,
        reasoning_summary=draft.reasoning_summary,
    )
    session.add(assessment)
    try:
        await session.commit()
    except Exception as exc:
        await session.rollback()
        raise TopicAssessmentError(
            f"Failed to persist topic assessment: {exc}",
            cause=exc,
        ) from exc
    await session.refresh(assessment)

    return AssessTopicResult(
        assessment=assessment,
        created=True,
        model_version=result.model_version,
        prompt_version=result.prompt_version,
        evidence=evidence,
    )
