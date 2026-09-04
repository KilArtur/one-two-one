"""Stop-factor assessment from transcripts (M6 / TASK-017, Р6)."""

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
    Recommendation,
    StopFactorFlag,
)
from app.prompts import load_prompt


class StopFactorAssessmentError(Exception):
    """LLM or validation failure while assessing stop-factors."""

    def __init__(self, message: str, *, cause: BaseException | None = None) -> None:
        super().__init__(message)
        self.cause = cause


class _EvidenceDraft(BaseModel):
    """Single evidence quote from structured LLM output."""

    quote: str = Field(min_length=1)
    timecode_sec: float = Field(ge=0)
    answer_id: str | None = None


class _FactorDraft(BaseModel):
    """LLM judgement for one vacancy stop-factor."""

    stop_factor: str = Field(min_length=1)
    triggered: bool
    confidence: Confidence
    evidence: list[_EvidenceDraft] = Field(default_factory=list)
    reasoning_summary: str = Field(min_length=1)


class _StopFactorsLLMOutput(BaseModel):
    """Native structured output for stop-factor assessment."""

    factors: list[_FactorDraft] = Field(default_factory=list)


@dataclass(frozen=True, slots=True)
class StopFactorHit:
    """One stop-factor after the deterministic Р6 gate."""

    stop_factor: str
    triggered: bool
    confidence: Confidence
    evidence: list[dict[str, Any]]
    reasoning_summary: str


@dataclass(slots=True)
class AssessStopFactorsResult:
    """Persisted flag plus recommendation impact of Р6."""

    flag: StopFactorFlag
    created: bool
    triggered: bool
    recommendation: Recommendation
    evidence: list[dict[str, Any]] = field(default_factory=list)
    factors: list[StopFactorHit] = field(default_factory=list)
    model_version: str | None = None
    prompt_version: str | None = None


def resolve_stop_factor_trigger(
    *,
    llm_triggered: bool,
    confidence: Confidence,
    evidence: list[Any],
) -> bool:
    """Р6 gate: auto-reject only on explicit + high confidence + evidence."""
    return (
        llm_triggered
        and confidence is Confidence.HIGH
        and len(evidence) > 0
    )


def recommendation_with_stop_factor(*, triggered: bool) -> Recommendation:
    """Map stop-factor flag to recommendation impact (feeds TASK-018 / Р5)."""
    if triggered:
        return Recommendation.NOT_SUITABLE
    # No auto-reject; human path when only stop-factors were considered.
    return Recommendation.NEEDS_ADDITIONAL_CHECK


def _evidence_dicts(
    drafts: list[_EvidenceDraft],
    *,
    answer_id_by_default: uuid.UUID | None,
) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in drafts:
        aid = item.answer_id or (
            str(answer_id_by_default) if answer_id_by_default is not None else None
        )
        entry: dict[str, Any] = {
            "quote": item.quote,
            "timecode_sec": item.timecode_sec,
        }
        if aid is not None:
            entry["answer_id"] = aid
        result.append(entry)
    return result


def _apply_r6_gate(drafts: list[_FactorDraft]) -> list[StopFactorHit]:
    hits: list[StopFactorHit] = []
    for draft in drafts:
        evidence = _evidence_dicts(draft.evidence, answer_id_by_default=None)
        triggered = resolve_stop_factor_trigger(
            llm_triggered=draft.triggered,
            confidence=draft.confidence,
            evidence=evidence,
        )
        hits.append(
            StopFactorHit(
                stop_factor=draft.stop_factor,
                triggered=triggered,
                confidence=draft.confidence,
                evidence=evidence if triggered else [],
                reasoning_summary=draft.reasoning_summary,
            )
        )
    return hits


def _hits_to_json(hits: list[StopFactorHit]) -> list[dict[str, Any]]:
    return [
        {
            "stop_factor": hit.stop_factor,
            "triggered": hit.triggered,
            "confidence": hit.confidence.value,
            "evidence": hit.evidence,
            "reasoning_summary": hit.reasoning_summary,
        }
        for hit in hits
    ]


def _triggered_evidence(hits: list[StopFactorHit]) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    for hit in hits:
        if not hit.triggered:
            continue
        for item in hit.evidence:
            collected.append({**item, "stop_factor": hit.stop_factor})
    return collected


def _build_user_prompt(
    *,
    stop_factors: list[str],
    answers: list[tuple[Answer, Question]],
) -> str:
    payload = {
        "stop_factors": stop_factors,
        "answers": [
            {
                "answer_id": str(answer.id),
                "question_id": str(question.id),
                "question_text": question.text,
                "transcript": answer.transcript,
                "transcript_segments": answer.transcript_segments,
                "skipped": answer.skipped,
                "technically_lost": answer.technically_lost,
            }
            for answer, question in answers
        ],
    }
    return (
        "Check vacancy stop-factors against the candidate answers (R6).\n"
        "Trigger only on explicit unambiguous statements with high confidence "
        "and verbatim evidence quotes with timecodes.\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


async def _load_existing(
    session: AsyncSession,
    *,
    candidate_id: uuid.UUID,
) -> StopFactorFlag | None:
    result = await session.execute(
        select(StopFactorFlag).where(StopFactorFlag.candidate_id == candidate_id)
    )
    return result.scalar_one_or_none()


async def assess_stop_factors(
    session: AsyncSession,
    *,
    candidate_id: uuid.UUID,
    stop_factors: list[str],
    answers: list[tuple[Answer, Question]],
    llm: LLMClient | None = None,
) -> AssessStopFactorsResult:
    """Assess vacancy stop-factors; persist flag separately from topics (Р6).

    Idempotent: if a flag already exists for the candidate, return it without
    calling the LLM.
    """
    existing = await _load_existing(session, candidate_id=candidate_id)
    if existing is not None:
        recommendation = recommendation_with_stop_factor(triggered=existing.triggered)
        return AssessStopFactorsResult(
            flag=existing,
            created=False,
            triggered=existing.triggered,
            recommendation=recommendation,
            evidence=list(existing.evidence),
            factors=[],
            model_version=existing.model_version or None,
            prompt_version=existing.prompt_version or None,
        )

    # No configured stop-factors → never auto-reject.
    if not stop_factors:
        flag = StopFactorFlag(
            candidate_id=candidate_id,
            triggered=False,
            factors=[],
            evidence=[],
            reasoning_summary="Vacancy has no stop-factors configured",
            model_version="",
            prompt_version="",
        )
        session.add(flag)
        await session.commit()
        await session.refresh(flag)
        return AssessStopFactorsResult(
            flag=flag,
            created=True,
            triggered=False,
            recommendation=recommendation_with_stop_factor(triggered=False),
            evidence=[],
            factors=[],
        )

    # Empty / only skipped answers → nothing explicit to trigger on.
    usable = [
        (answer, question)
        for answer, question in answers
        if (
            not answer.skipped
            and not answer.technically_lost
            and answer.transcript.strip()
        )
    ]
    if not usable:
        flag = StopFactorFlag(
            candidate_id=candidate_id,
            triggered=False,
            factors=[
                {
                    "stop_factor": text,
                    "triggered": False,
                    "confidence": Confidence.LOW.value,
                    "evidence": [],
                    "reasoning_summary": "No usable answer transcript to evaluate",
                }
                for text in stop_factors
            ],
            evidence=[],
            reasoning_summary="No usable transcripts; stop-factors not triggered",
            model_version="",
            prompt_version="",
        )
        session.add(flag)
        await session.commit()
        await session.refresh(flag)
        return AssessStopFactorsResult(
            flag=flag,
            created=True,
            triggered=False,
            recommendation=recommendation_with_stop_factor(triggered=False),
            evidence=[],
        )

    prompt = load_prompt("assess_stop_factors")
    client = llm if llm is not None else LLMClient()
    user_prompt = _build_user_prompt(stop_factors=stop_factors, answers=usable)

    try:
        result = await client.acomplete_structured(
            user_prompt,
            _StopFactorsLLMOutput,
            prompt_version=prompt.version,
            role=LLMRole.QUALITY,
            system=prompt.body,
        )
    except LLMError as exc:
        raise StopFactorAssessmentError(
            f"Stop-factor assessment LLM call failed: {exc}",
            cause=exc,
        ) from exc

    hits = _apply_r6_gate(result.content.factors)
    # Only evaluate factors that belong to the vacancy list.
    allowed = set(stop_factors)
    hits = [hit for hit in hits if hit.stop_factor in allowed]
    triggered = any(hit.triggered for hit in hits)
    evidence = _triggered_evidence(hits)
    summary_parts = [
        f"{hit.stop_factor}: {hit.reasoning_summary}"
        for hit in hits
        if hit.triggered
    ]
    reasoning = (
        "; ".join(summary_parts)
        if summary_parts
        else "No stop-factor triggered with high confidence and evidence"
    )

    flag = StopFactorFlag(
        candidate_id=candidate_id,
        triggered=triggered,
        factors=_hits_to_json(hits),
        evidence=evidence,
        reasoning_summary=reasoning,
        model_version=result.model_version,
        prompt_version=result.prompt_version,
    )
    session.add(flag)
    try:
        await session.commit()
    except Exception as exc:
        await session.rollback()
        raise StopFactorAssessmentError(
            f"Failed to persist stop-factor flag: {exc}",
            cause=exc,
        ) from exc
    await session.refresh(flag)

    return AssessStopFactorsResult(
        flag=flag,
        created=True,
        triggered=triggered,
        recommendation=recommendation_with_stop_factor(triggered=triggered),
        evidence=evidence,
        factors=hits,
        model_version=result.model_version,
        prompt_version=result.prompt_version,
    )
