"""Оценка стоп-факторов (Р6): авто «не подходит» только при явном ответе с high confidence.

Сигналы даёт LLM; детерминированное правило `resolve_stop_factor` решает, срабатывает ли
стоп-фактор: только явное однозначное подтверждение при высокой уверенности и с цитатой.
Иначе флаг не срабатывает — случай уходит человеку. Флаг хранится в отдельной таблице
`stop_factor_flag`, независимо от оценки топиков.
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.llm import LangChainLLMClient, get_llm_client
from app.models.answer import Answer
from app.models.question import Question
from app.models.stop_factor import StopFactorFlag
from app.models.topic_assessment import AssessmentConfidence
from app.prompts import load_prompt
from app.schemas.assessment import StopFactorLLM
from app.services.evidence import locate_evidence

STOP_FACTOR_PROMPT = "stop_factor"
STOP_FACTOR_PROMPT_VERSION = "stop-factor-v1"


def resolve_stop_factor(
    *,
    triggered_explicitly: bool,
    confidence: AssessmentConfidence,
    has_evidence: bool,
) -> bool:
    """Правило Р6: срабатывание только при явном ответе, high confidence и наличии цитаты."""
    return (
        triggered_explicitly
        and confidence == AssessmentConfidence.HIGH
        and has_evidence
    )


def _transcript_text(answer: Answer) -> str:
    if answer.transcript:
        return answer.transcript
    segments = answer.transcript_segments or []
    return "\n".join(str(segment.get("text", "")) for segment in segments)


async def evaluate_stop_factor(
    session: AsyncSession,
    candidate_id: uuid.UUID,
    answer_id: uuid.UUID,
    stop_factor: str,
    *,
    llm_client: LangChainLLMClient | None = None,
) -> StopFactorFlag | None:
    """Оценивает один стоп-фактор по ответу и сохраняет флаг (отдельно от топиков)."""
    llm_client = llm_client or get_llm_client()

    answer = await session.get(Answer, answer_id)
    if answer is None:
        return None
    question = await session.get(Question, answer.question_id)
    if question is None:
        return None

    template = load_prompt(STOP_FACTOR_PROMPT)
    prompt = template.format(
        stop_factor=stop_factor,
        question_text=question.text,
        transcript=_transcript_text(answer) or "—",
    )
    result = await llm_client.generate_structured(
        prompt,
        schema=StopFactorLLM,
        prompt_version=STOP_FACTOR_PROMPT_VERSION,
    )
    verdict: StopFactorLLM = result.content

    evidence: dict[str, Any] | None = locate_evidence(
        answer.transcript_segments,
        verdict.evidence_quote,
        question_id=answer.question_id,
    )
    triggered = resolve_stop_factor(
        triggered_explicitly=verdict.triggered_explicitly,
        confidence=verdict.confidence,
        has_evidence=evidence is not None,
    )

    flag = StopFactorFlag(
        candidate_id=candidate_id,
        stop_factor=stop_factor,
        triggered=triggered,
        confidence=verdict.confidence,
        evidence=evidence if triggered else None,
        reasoning_summary=verdict.reasoning_summary,
    )
    session.add(flag)
    await session.commit()
    await session.refresh(flag)
    return flag


async def candidate_stop_factor_triggered(
    session: AsyncSession, candidate_id: uuid.UUID
) -> bool:
    """Возвращает True, если у кандидата есть хотя бы один сработавший стоп-фактор (для Р5)."""
    triggered = await session.scalar(
        select(StopFactorFlag.id).where(
            StopFactorFlag.candidate_id == candidate_id,
            StopFactorFlag.triggered.is_(True),
        )
    )
    return triggered is not None
