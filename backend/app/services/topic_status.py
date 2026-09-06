"""Детерминированное правило статуса топика (Р13) как чистая функция от сигналов.

Не обращается к LLM/сети/БД: вход — три сигнала Р13, категориальная уверенность и
явные флаги (пропуск, отсутствие опыта, техническая ошибка), выход — статус топика.
Статус `out_of_scope` этой функцией не назначается — его ставит человек вручную (Р15).
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from app.models.topic_assessment import AssessmentConfidence, AssessmentStatus


@dataclass(slots=True, frozen=True)
class TopicSignals:
    """Три сигнала Р13: техническая корректность, конкретный пример, личный вклад."""

    correctness: bool = False
    example: bool = False
    personal_contribution: bool = False

    @classmethod
    def from_mapping(cls, data: Mapping[str, object] | None) -> TopicSignals:
        """Собирает сигналы из jsonb-словаря оценки (недостающие ключи — False)."""
        data = data or {}
        return cls(
            correctness=bool(data.get("correctness", False)),
            example=bool(data.get("example", False)),
            personal_contribution=bool(data.get("personal_contribution", False)),
        )

    @property
    def all_present(self) -> bool:
        """Все три сигнала присутствуют."""
        return self.correctness and self.example and self.personal_contribution


def resolve_topic_status(
    *,
    signals: TopicSignals,
    confidence: AssessmentConfidence,
    explicit_no_experience: bool = False,
    technical_error: bool = False,
    skipped: bool = False,
) -> AssessmentStatus:
    """Возвращает статус топика по правилу Р13.

    - осознанный пропуск вопроса → `not_confirmed`;
    - явное отсутствие опыта или уклонение от ответа («нет идей» и т.п.) →
      `not_confirmed`;
    - при высокой уверенности: существенная техническая ошибка → `not_confirmed`;
      все три сигнала → `confirmed`; иначе → `needs_check`;
    - любая средняя/низкая уверенность (без уклонения) → `needs_check`.
    """
    if skipped or explicit_no_experience:
        return AssessmentStatus.NOT_CONFIRMED

    if confidence == AssessmentConfidence.HIGH:
        if technical_error:
            return AssessmentStatus.NOT_CONFIRMED
        if signals.all_present:
            return AssessmentStatus.CONFIRMED
        return AssessmentStatus.NEEDS_CHECK

    return AssessmentStatus.NEEDS_CHECK
