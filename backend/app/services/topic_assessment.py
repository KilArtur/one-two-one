"""Оценка топика из транскрипта через LLM с evidence и изоляцией топиков (Р16).

Сигналы и уверенность даёт LLM (по одному топику, с явной инструкцией игнорировать
чужие технологии — Р16). Итоговый статус вычисляет детерминированное правило Р13
(`resolve_topic_status`). `system_status` фиксируется при создании и никогда не
перезаписывается: повторный вызов возвращает уже существующую оценку без изменений.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.llm import LangChainLLMClient, get_llm_client
from app.models.answer import Answer
from app.models.question import Question
from app.models.topic import Topic
from app.models.topic_assessment import (
    AssessmentConfidence,
    AssessmentStatus,
    ReviewerRole,
    StatusChangeLog,
    TopicAssessment,
)
from app.prompts import load_prompt
from app.schemas.assessment import TopicAssessmentLLM
from app.services.auth import CurrentUser, ensure_topic_status_change_allowed
from app.services.evidence import locate_evidence
from app.services.topic_status import TopicSignals, resolve_topic_status

_AUTHOR_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-0000000000a2")

TOPIC_ASSESSMENT_PROMPT = "topic_assessment"
TOPIC_ASSESSMENT_PROMPT_VERSION = "topic-assessment-v1"


def _transcript_text(answer: Answer) -> str:
    """Возвращает текст транскрипта: полный текст или склейку сегментов."""
    if answer.transcript:
        return answer.transcript
    segments = answer.transcript_segments or []
    return "\n".join(str(segment.get("text", "")) for segment in segments)


def format_topic_assessment_prompt(
    *,
    topic_title: str,
    skill_type: str,
    requirement_description: str | None,
    depth_expectations: str | None,
    question_text: str,
    transcript: str,
) -> str:
    """Готовит промпт оценки одного топика из плоских полей (без ORM), Р16."""
    template = load_prompt(TOPIC_ASSESSMENT_PROMPT)
    return template.format(
        topic_title=topic_title,
        skill_type=skill_type,
        requirement_description=requirement_description or "—",
        depth_expectations=depth_expectations or "—",
        question_text=question_text,
        transcript=transcript or "—",
    )


def build_prompt(topic: Topic, question: Question, answer: Answer) -> str:
    """Готовит промпт оценки одного топика (только его требование, Р16)."""
    return format_topic_assessment_prompt(
        topic_title=topic.title,
        skill_type=topic.skill_type.value,
        requirement_description=topic.requirement_description,
        depth_expectations=topic.depth_expectations,
        question_text=question.text,
        transcript=_transcript_text(answer),
    )


async def assess_topic(
    session: AsyncSession,
    candidate_id: uuid.UUID,
    answer_id: uuid.UUID,
    *,
    llm_client: LangChainLLMClient | None = None,
) -> TopicAssessment | None:
    """Оценивает топик по ответу и сохраняет `TopicAssessment` (system_status фиксирован)."""
    llm_client = llm_client or get_llm_client()

    answer = await session.get(Answer, answer_id)
    if answer is None:
        return None
    question = await session.get(Question, answer.question_id)
    if question is None:
        return None
    topic = await session.get(Topic, question.topic_id)
    if topic is None:
        return None

    existing = await session.scalar(
        select(TopicAssessment).where(
            TopicAssessment.candidate_id == candidate_id,
            TopicAssessment.topic_id == topic.id,
        )
    )
    if existing is not None:
        return existing

    if answer.skipped:
        status = resolve_topic_status(
            signals=TopicSignals(),
            confidence=AssessmentConfidence.HIGH,
            skipped=True,
        )
        assessment = TopicAssessment(
            candidate_id=candidate_id,
            topic_id=topic.id,
            system_status=status,
            current_status=status,
            confidence=AssessmentConfidence.HIGH,
            signals={"correctness": False, "example": False, "personal_contribution": False},
            evidence=None,
            reasoning_summary="Вопрос осознанно пропущен кандидатом.",
        )
        session.add(assessment)
        await session.commit()
        await session.refresh(assessment)
        return assessment

    result = await llm_client.generate_structured(
        build_prompt(topic, question, answer),
        schema=TopicAssessmentLLM,
        prompt_version=TOPIC_ASSESSMENT_PROMPT_VERSION,
    )
    verdict: TopicAssessmentLLM = result.content

    signals = TopicSignals(
        correctness=verdict.correctness,
        example=verdict.example,
        personal_contribution=verdict.personal_contribution,
    )
    status = resolve_topic_status(
        signals=signals,
        confidence=verdict.confidence,
        explicit_no_experience=verdict.explicit_no_experience,
        technical_error=verdict.technical_error,
    )
    evidence_item = locate_evidence(
        answer.transcript_segments,
        verdict.evidence_quote,
        question_id=answer.question_id,
    )
    evidence: list[dict[str, Any]] | None = [evidence_item] if evidence_item else None

    assessment = TopicAssessment(
        candidate_id=candidate_id,
        topic_id=topic.id,
        system_status=status,
        current_status=status,
        confidence=verdict.confidence,
        signals={
            "correctness": verdict.correctness,
            "example": verdict.example,
            "personal_contribution": verdict.personal_contribution,
        },
        evidence=evidence,
        reasoning_summary=verdict.reasoning_summary,
    )
    session.add(assessment)
    await session.commit()
    await session.refresh(assessment)
    return assessment


async def change_topic_status(
    session: AsyncSession,
    assessment_id: uuid.UUID,
    *,
    user: CurrentUser,
    new_status: AssessmentStatus,
    comment: str,
) -> TopicAssessment | None:
    """Меняет current_status экспертом (RBAC + обязательный комментарий, Р21).

    `system_status` не перезаписывается никогда; каждая смена — append-only запись
    в StatusChangeLog. Право зависит от типа топика (hard → техспец, soft → НМ).
    """
    assessment = await session.get(TopicAssessment, assessment_id)
    if assessment is None:
        return None
    topic = await session.get(Topic, assessment.topic_id)
    if topic is None:
        return None

    ensure_topic_status_change_allowed(user, topic.skill_type)

    old_status = assessment.current_status
    assessment.current_status = new_status
    assessment.reviewer_comment = comment
    assessment.reviewed_by = uuid.uuid5(_AUTHOR_NAMESPACE, user.username)
    session.add(
        StatusChangeLog(
            assessment_id=assessment.id,
            author_id=uuid.uuid5(_AUTHOR_NAMESPACE, user.username),
            author_role=ReviewerRole(user.role.value),
            old_status=old_status,
            new_status=new_status,
            comment=comment,
        )
    )
    await session.commit()
    await session.refresh(assessment)
    return assessment
