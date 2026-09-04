"""Детерминированная итоговая рекомендация (Р5) как чистая функция от матрицы топиков.

Без вызова LLM. Учитываются только обязательные (mandatory) топики; топики «вне зоны
интервью» (out_of_scope) исключаются из расчёта. Желательные топики на рекомендацию не
влияют. Сработавший стоп-фактор эквивалентен обязательному «не подтверждено».
"""

from __future__ import annotations

from collections.abc import Iterable

from app.models.interview_result import InterviewRecommendation
from app.models.topic import TopicImportance
from app.models.topic_assessment import AssessmentStatus
from app.services.matrix import TopicOutcome


def compute_recommendation(
    outcomes: Iterable[TopicOutcome],
    *,
    stop_factor_triggered: bool = False,
) -> InterviewRecommendation:
    """Возвращает рекомендацию по кандидату по правилу Р5 (M6)."""
    mandatory = [
        outcome
        for outcome in outcomes
        if outcome.importance == TopicImportance.MANDATORY
        and outcome.status != AssessmentStatus.OUT_OF_SCOPE
    ]

    if stop_factor_triggered or any(
        outcome.status == AssessmentStatus.NOT_CONFIRMED for outcome in mandatory
    ):
        return InterviewRecommendation.NOT_FIT

    if any(outcome.status == AssessmentStatus.NEEDS_CHECK for outcome in mandatory):
        return InterviewRecommendation.ADDITIONAL_CHECK

    return InterviewRecommendation.FIT
