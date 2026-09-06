"""Расчёт Coverage (Р4) как чистая функция от матрицы топиков.

Тройка чисел (подтверждено/требует проверки/не подтверждено) считается всегда по всем
топикам в зоне интервью. `mandatory_coverage` и `desired_coverage` — доли подтверждённых
по правилу Р4: `None`, пока в группе есть спорные (needs_check).

Дополнительно считаются доли для UI:
- `mandatory_confirmed_share` / `desired_confirmed_share` — подтверждённые / всего в группе
  (всегда, даже при спорных);
- `mandatory_potential_share` — (подтверждённые + требует проверки) / обязательные.

Топики «вне зоны интервью» исключаются из знаменателя. Единый балл/AI-score не вычисляется.
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
    mandatory_confirmed_share: Decimal | None
    desired_confirmed_share: Decimal | None
    mandatory_potential_share: Decimal | None


def _group(in_scope: Sequence[TopicOutcome], importance: TopicImportance) -> list[TopicOutcome]:
    return [outcome for outcome in in_scope if outcome.importance == importance]


def _share(group: Sequence[TopicOutcome], *statuses: AssessmentStatus) -> Decimal | None:
    if not group:
        return None
    matched = sum(1 for outcome in group if outcome.status in statuses)
    return (Decimal(matched) / Decimal(len(group))).quantize(_QUANTUM)


def _coverage_for(in_scope: Sequence[TopicOutcome], importance: TopicImportance) -> Decimal | None:
    """Доля подтверждённых в группе по Р4; None пока есть спорные или группа пуста."""
    group = _group(in_scope, importance)
    if not group:
        return None
    if any(outcome.status == AssessmentStatus.NEEDS_CHECK for outcome in group):
        return None
    return _share(group, AssessmentStatus.CONFIRMED)


def compute_coverage(outcomes: Iterable[TopicOutcome]) -> CoverageResult:
    """Считает тройку чисел и доли покрытия по Р4 + доли для UI."""
    in_scope = [outcome for outcome in outcomes if outcome.status != AssessmentStatus.OUT_OF_SCOPE]
    mandatory = _group(in_scope, TopicImportance.MANDATORY)
    desired = _group(in_scope, TopicImportance.DESIRED)
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
        mandatory_confirmed_share=_share(mandatory, AssessmentStatus.CONFIRMED),
        desired_confirmed_share=_share(desired, AssessmentStatus.CONFIRMED),
        mandatory_potential_share=_share(
            mandatory, AssessmentStatus.CONFIRMED, AssessmentStatus.NEEDS_CHECK
        ),
    )
