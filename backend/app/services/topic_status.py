"""Deterministic topic status rule Р13 (pure function, no I/O)."""

from __future__ import annotations

from dataclasses import dataclass

from app.models.enums import Confidence, TopicStatus


@dataclass(frozen=True, slots=True)
class TopicSignals:
    """Three boolean signals from assessment (PRD §5 / Р13)."""

    correctness: bool
    example: bool
    personal_contribution: bool

    @property
    def all_positive(self) -> bool:
        return self.correctness and self.example and self.personal_contribution


def resolve_topic_status(
    *,
    signals: TopicSignals,
    confidence: Confidence,
    question_skipped: bool = False,
    no_experience: bool = False,
) -> TopicStatus:
    """Map signals + confidence to topic status (Р13).

    - confirmed: all three signals + high confidence
    - not_confirmed: conscious skip, explicit no experience, or
      substantial technical error (correctness=False) with high confidence
    - needs_check: default for everything else (incl. low/medium confidence)
    """
    if question_skipped or no_experience:
        return TopicStatus.NOT_CONFIRMED

    if confidence != Confidence.HIGH:
        return TopicStatus.NEEDS_CHECK

    if signals.all_positive:
        return TopicStatus.CONFIRMED

    if not signals.correctness:
        return TopicStatus.NOT_CONFIRMED

    return TopicStatus.NEEDS_CHECK
