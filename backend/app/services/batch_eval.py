"""Batch-оценка существующих транскриптов без видео (ключ Этапа 1 PRD).

Читает транскрипты по топикам (JSON/CSV), оценивает каждый топик через LLM (изоляция
Р16), считает статус по детерминированному правилу Р13, а затем рекомендацию (Р5) и
Coverage (Р4) по каждому кандидату. Ничего не пишет в БД и не требует видео — только
транскрипты. Детерминированный слой воспроизводим: при тех же сигналах и `prompt_version`
результат совпадает.
"""

from __future__ import annotations

import csv
import json
import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any

from app.integrations.llm import LangChainLLMClient, get_llm_client
from app.models.topic import SkillType, TopicImportance
from app.models.topic_assessment import AssessmentConfidence, AssessmentStatus
from app.schemas.assessment import TopicAssessmentLLM
from app.services.coverage import compute_coverage
from app.services.evidence import locate_evidence
from app.services.matrix import TopicOutcome
from app.services.recommendation import compute_recommendation
from app.services.topic_assessment import (
    TOPIC_ASSESSMENT_PROMPT_VERSION,
    format_topic_assessment_prompt,
)
from app.services.topic_status import TopicSignals, resolve_topic_status

_NAMESPACE = uuid.UUID("00000000-0000-0000-0000-0000000000b1")


@dataclass(slots=True, frozen=True)
class BatchTopicInput:
    """Один топик кандидата с транскриптом ответа."""

    title: str
    skill_type: SkillType
    importance: TopicImportance
    question_text: str
    transcript_segments: list[dict[str, Any]]
    requirement_description: str | None = None
    depth_expectations: str | None = None
    skipped: bool = False


@dataclass(slots=True, frozen=True)
class BatchCandidateInput:
    """Кандидат с набором топиков."""

    id: str
    topics: list[BatchTopicInput]


def _transcript_text(segments: Sequence[dict[str, Any]]) -> str:
    return "\n".join(str(segment.get("text", "")) for segment in segments)


async def _evaluate_topic(
    candidate_id: str,
    topic: BatchTopicInput,
    *,
    llm_client: LangChainLLMClient,
) -> dict[str, Any]:
    question_id = uuid.uuid5(_NAMESPACE, f"{candidate_id}:{topic.title}")

    if topic.skipped:
        status = resolve_topic_status(
            signals=TopicSignals(), confidence=AssessmentConfidence.HIGH, skipped=True
        )
        return {
            "title": topic.title,
            "importance": topic.importance.value,
            "status": status.value,
            "confidence": AssessmentConfidence.HIGH.value,
            "signals": {"correctness": False, "example": False, "personal_contribution": False},
            "evidence": None,
            "reasoning": "Вопрос осознанно пропущен.",
        }

    prompt = format_topic_assessment_prompt(
        topic_title=topic.title,
        skill_type=topic.skill_type.value,
        requirement_description=topic.requirement_description,
        depth_expectations=topic.depth_expectations,
        question_text=topic.question_text,
        transcript=_transcript_text(topic.transcript_segments),
    )
    result = await llm_client.generate_structured(
        prompt, schema=TopicAssessmentLLM, prompt_version=TOPIC_ASSESSMENT_PROMPT_VERSION
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
    evidence = locate_evidence(
        topic.transcript_segments, verdict.evidence_quote, question_id=question_id
    )
    return {
        "title": topic.title,
        "importance": topic.importance.value,
        "status": status.value,
        "confidence": verdict.confidence.value,
        "signals": {
            "correctness": verdict.correctness,
            "example": verdict.example,
            "personal_contribution": verdict.personal_contribution,
        },
        "evidence": evidence,
        "reasoning": verdict.reasoning_summary,
    }


def _coverage_value(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None


async def evaluate_candidate(
    candidate: BatchCandidateInput, *, llm_client: LangChainLLMClient
) -> dict[str, Any]:
    """Оценивает все топики кандидата и собирает статус + рекомендацию + coverage."""
    topics_report = [
        await _evaluate_topic(candidate.id, topic, llm_client=llm_client)
        for topic in candidate.topics
    ]
    outcomes = [
        TopicOutcome(
            importance=TopicImportance(item["importance"]),
            status=AssessmentStatus(item["status"]),
        )
        for item in topics_report
    ]
    coverage = compute_coverage(outcomes)
    recommendation = compute_recommendation(outcomes)
    return {
        "id": candidate.id,
        "recommendation": recommendation.value,
        "coverage": {
            "confirmed": coverage.confirmed_count,
            "needs_check": coverage.needs_check_count,
            "not_confirmed": coverage.not_confirmed_count,
            "mandatory_coverage": _coverage_value(coverage.mandatory_coverage),
            "desired_coverage": _coverage_value(coverage.desired_coverage),
        },
        "topics": topics_report,
    }


async def run_batch(
    candidates: Iterable[BatchCandidateInput],
    *,
    llm_client: LangChainLLMClient | None = None,
    model_version: str = "unspecified",
    prompt_version: str = TOPIC_ASSESSMENT_PROMPT_VERSION,
) -> dict[str, Any]:
    """Прогоняет batch-оценку и возвращает отчёт."""
    llm_client = llm_client or get_llm_client()
    reports = [
        await evaluate_candidate(candidate, llm_client=llm_client) for candidate in candidates
    ]
    return {
        "prompt_version": prompt_version,
        "model_version": model_version,
        "candidates": reports,
    }


def _parse_topic(raw: dict[str, Any]) -> BatchTopicInput:
    segments = raw.get("transcript_segments")
    if segments is None and raw.get("transcript"):
        segments = [{"text": raw["transcript"], "start": 0, "end": 0}]
    return BatchTopicInput(
        title=raw["title"],
        skill_type=SkillType(raw["skill_type"]),
        importance=TopicImportance(raw["importance"]),
        question_text=raw.get("question_text", ""),
        transcript_segments=list(segments or []),
        requirement_description=raw.get("requirement_description"),
        depth_expectations=raw.get("depth_expectations"),
        skipped=bool(raw.get("skipped", False)),
    )


def parse_candidates(raw: dict[str, Any] | list[dict[str, Any]]) -> list[BatchCandidateInput]:
    """Собирает кандидатов из разобранного JSON (объект с `candidates` или список)."""
    items = raw["candidates"] if isinstance(raw, dict) else raw
    return [
        BatchCandidateInput(
            id=str(candidate["id"]),
            topics=[_parse_topic(topic) for topic in candidate["topics"]],
        )
        for candidate in items
    ]


def _load_csv(path: Path) -> list[BatchCandidateInput]:
    grouped: dict[str, list[BatchTopicInput]] = {}
    order: list[str] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            candidate_id = str(row["candidate_id"])
            if candidate_id not in grouped:
                grouped[candidate_id] = []
                order.append(candidate_id)
            grouped[candidate_id].append(
                _parse_topic(
                    {
                        "title": row["title"],
                        "skill_type": row["skill_type"],
                        "importance": row["importance"],
                        "question_text": row.get("question_text", ""),
                        "transcript": row.get("transcript", ""),
                        "requirement_description": row.get("requirement_description"),
                        "depth_expectations": row.get("depth_expectations"),
                        "skipped": row.get("skipped", "").strip().lower() in {"1", "true", "yes"},
                    }
                )
            )
    return [BatchCandidateInput(id=cid, topics=grouped[cid]) for cid in order]


def load_input(path: str | Path) -> list[BatchCandidateInput]:
    """Загружает кандидатов из JSON или CSV по расширению файла."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        return _load_csv(path)
    return parse_candidates(json.loads(path.read_text(encoding="utf-8")))
