"""Сравнение system-оценки с экспертной разметкой для приёмочной метрики 80%."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from app.models.interview_result import InterviewRecommendation
from app.models.topic_assessment import AssessmentStatus

RECOMMENDATION_CLASSES = [
    InterviewRecommendation.FIT.value,
    InterviewRecommendation.ADDITIONAL_CHECK.value,
    InterviewRecommendation.NOT_FIT.value,
]
TOPIC_STATUS_CLASSES = [
    AssessmentStatus.CONFIRMED.value,
    AssessmentStatus.NEEDS_CHECK.value,
    AssessmentStatus.NOT_CONFIRMED.value,
    AssessmentStatus.OUT_OF_SCOPE.value,
]


def _round_ratio(matched: int, total: int) -> float | None:
    if total == 0:
        return None
    return round(matched / total, 4)


def _empty_confusion_matrix(labels: list[str]) -> dict[str, dict[str, int]]:
    return {expected: {actual: 0 for actual in labels} for expected in labels}


def _status_from_topic(topic: dict[str, Any]) -> str:
    if "system_status" in topic:
        return str(topic["system_status"])
    if "status" in topic:
        return str(topic["status"])
    raise ValueError("Topic entry must contain 'system_status' or 'status'")


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _load_expert_csv(path: Path) -> dict[str, Any]:
    grouped: dict[str, dict[str, Any]] = {}
    order: list[str] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            candidate_id = str(row["candidate_id"])
            candidate = grouped.get(candidate_id)
            if candidate is None:
                candidate = {
                    "id": candidate_id,
                    "recommendation": row["recommendation"],
                    "topics": [],
                }
                grouped[candidate_id] = candidate
                order.append(candidate_id)
            candidate["topics"].append(
                {
                    "title": row["topic_title"],
                    "system_status": row["system_status"],
                }
            )
    return {"candidates": [grouped[candidate_id] for candidate_id in order]}


def load_comparison_input(path: str | Path) -> dict[str, Any]:
    """Загружает system-report или экспертную разметку из JSON/CSV."""
    path = Path(path)
    if path.suffix.lower() == ".csv":
        return _load_expert_csv(path)
    return _load_json(path)


def compare_with_expert(
    system_report: dict[str, Any],
    expert_labels: dict[str, Any],
    *,
    agreement_threshold: float = 0.8,
) -> dict[str, Any]:
    """Считает совпадение рекомендации и `system_status` с экспертной разметкой."""
    system_candidates = {
        str(candidate["id"]): candidate for candidate in system_report.get("candidates", [])
    }
    expert_candidates = {
        str(candidate["id"]): candidate for candidate in expert_labels.get("candidates", [])
    }
    shared_candidate_ids = sorted(system_candidates.keys() & expert_candidates.keys())

    recommendation_confusion = _empty_confusion_matrix(RECOMMENDATION_CLASSES)
    recommendation_matched = 0

    for candidate_id in shared_candidate_ids:
        expert_recommendation = str(expert_candidates[candidate_id]["recommendation"])
        system_recommendation = str(system_candidates[candidate_id]["recommendation"])
        recommendation_confusion[expert_recommendation][system_recommendation] += 1
        if expert_recommendation == system_recommendation:
            recommendation_matched += 1

    topic_status_confusion = _empty_confusion_matrix(TOPIC_STATUS_CLASSES)
    topic_status_matched = 0
    topic_status_total = 0

    for candidate_id in shared_candidate_ids:
        system_topics = {
            str(topic["title"]): topic
            for topic in system_candidates[candidate_id].get("topics", [])
        }
        expert_topics = {
            str(topic["title"]): topic
            for topic in expert_candidates[candidate_id].get("topics", [])
        }
        for topic_title in sorted(system_topics.keys() & expert_topics.keys()):
            expert_status = _status_from_topic(expert_topics[topic_title])
            system_status = _status_from_topic(system_topics[topic_title])
            topic_status_confusion[expert_status][system_status] += 1
            topic_status_total += 1
            if expert_status == system_status:
                topic_status_matched += 1

    recommendation_total = len(shared_candidate_ids)
    recommendation_rate = _round_ratio(recommendation_matched, recommendation_total)
    topic_status_rate = _round_ratio(topic_status_matched, topic_status_total)

    return {
        "recommendation_agreement": {
            "matched": recommendation_matched,
            "total": recommendation_total,
            "agreement_rate": recommendation_rate,
            "threshold": agreement_threshold,
            "passed": (
                recommendation_rate is not None and recommendation_rate >= agreement_threshold
            ),
        },
        "recommendation_confusion_matrix": recommendation_confusion,
        "topic_status_agreement": {
            "matched": topic_status_matched,
            "total": topic_status_total,
            "agreement_rate": topic_status_rate,
        },
        "topic_status_confusion_matrix": topic_status_confusion,
        "coverage": {
            "compared_candidates": recommendation_total,
            "compared_topic_statuses": topic_status_total,
            "missing_in_expert": sorted(system_candidates.keys() - expert_candidates.keys()),
            "missing_in_system": sorted(expert_candidates.keys() - system_candidates.keys()),
        },
    }
