"""Расчёт Coverage (Р4) как чистая функция от матрицы топиков.

Тройка чисел (подтверждено/требует проверки/не подтверждено) считается всегда по всем
топикам в зоне интервью. `mandatory_coverage` и `desired_coverage` — доли подтверждённых,
но только когда в группе нет спорных (needs_check): пока есть спорные — `None`. Топики
«вне зоны интервью» исключаются из знаменателя. Единый балл/AI-score не вычисляется.
"""

from __future__ import annotations

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.models.topic import TopicImportance
from app.models.topic_assessment import AssessmentStatus
from app.services.matrix import TopicOutcome

_QUANTUM = Decimal("0.0001")


@dataclass(slots=True, frozen=True)
class CoverageResult:
    """Покрытие требований: тройка чисел и доли по обязательным/желательным."""

    confirmed_count: int
    needs_check_count: int
    not_confirmed_count: int
    mandatory_coverage: Decimal | None
    desired_coverage: Decimal | None


def _coverage_for(
    in_scope: Sequence[TopicOutcome], importance: TopicImportance
) -> Decimal | None:
    """Доля подтверждённых в группе; None пока есть спорные или группа пуста."""
    group = [outcome for outcome in in_scope if outcome.importance == importance]
    if not group:
        return None
    if any(outcome.status == AssessmentStatus.NEEDS_CHECK for outcome in group):
        return None
    confirmed = sum(1 for outcome in group if outcome.status == AssessmentStatus.CONFIRMED)
    return (Decimal(confirmed) / Decimal(len(group))).quantize(_QUANTUM)


def compute_coverage(outcomes: Iterable[TopicOutcome]) -> CoverageResult:
    """Считает тройку чисел и доли покрытия по Р4."""
    in_scope = [
        outcome for outcome in outcomes if outcome.status != AssessmentStatus.OUT_OF_SCOPE
    ]
    return CoverageResult(
        confirmed_count=sum(
            1 for outcome in in_scope if outcome.status == AssessmentStatus.CONFIRMED
        ),
        needs_check_count=sum(
            1 for outcome in in_scope if outcome.status == AssessmentStatus.NEEDS_CHECK
        ),
        not_confirmed_count=sum(
            1 for outcome in in_scope if outcome.status == AssessmentStatus.NOT_CONFIRMED
        ),
        mandatory_coverage=_coverage_for(in_scope, TopicImportance.MANDATORY),
        desired_coverage=_coverage_for(in_scope, TopicImportance.DESIRED),
    )
