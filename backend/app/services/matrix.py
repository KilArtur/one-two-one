"""Вход для детерминированных расчётов по матрице топиков (рекомендация и coverage)."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.topic import TopicImportance
from app.models.topic_assessment import AssessmentStatus


@dataclass(slots=True, frozen=True)
class TopicOutcome:
    """Итог по одному топику: важность и статус покрытия."""

    importance: TopicImportance
    status: AssessmentStatus
