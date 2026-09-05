"""Детерминированная итоговая рекомендация (Р5) как чистая функция от матрицы топиков.

Без вызова LLM. Учитываются только обязательные (mandatory) топики; топики «вне зоны
интервью» (out_of_scope) исключаются из расчёта. Желательные топики на рекомендацию не
влияют. Единственное основание для авто «не подходит» — неподтверждённый обязательный топик.
"""

from __future__ import annotations

from collections.abc import Iterable

from app.models.interview_result import InterviewRecommendation
from app.models.topic import TopicImportance
from app.models.topic_assessment import AssessmentStatus
from app.services.matrix import TopicOutcome


def recommendation_with_reason(
    outcomes: Iterable[TopicOutcome],
) -> tuple[InterviewRecommendation, str]:
    """Возвращает рекомендацию Р5 и код причины (какая ветка правила сработала)."""
    mandatory = [
        outcome
        for outcome in outcomes
        if outcome.importance == TopicImportance.MANDATORY
        and outcome.status != AssessmentStatus.OUT_OF_SCOPE
    ]

    if any(outcome.status == AssessmentStatus.NOT_CONFIRMED for outcome in mandatory):
        return InterviewRecommendation.NOT_FIT, "mandatory_not_confirmed"
    if any(outcome.status == AssessmentStatus.NEEDS_CHECK for outcome in mandatory):
        return InterviewRecommendation.ADDITIONAL_CHECK, "mandatory_needs_check"
    return InterviewRecommendation.FIT, "all_mandatory_confirmed"


def compute_recommendation(outcomes: Iterable[TopicOutcome]) -> InterviewRecommendation:
    """Возвращает рекомендацию по кандидату по правилу Р5 (M6)."""
    recommendation, _ = recommendation_with_reason(outcomes)
    return recommendation
