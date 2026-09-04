"""Unit tests for deterministic topic status rule Р13 (TASK-015)."""

from __future__ import annotations

import pytest

from app.models.enums import Confidence, TopicStatus
from app.services.topic_status import TopicSignals, resolve_topic_status


def test_three_signals_high_confidence_confirmed() -> None:
    """Шаг 1: 3 сигнала + high confidence -> confirmed."""
    status = resolve_topic_status(
        signals=TopicSignals(
            correctness=True,
            example=True,
            personal_contribution=True,
        ),
        confidence=Confidence.HIGH,
    )
    assert status == TopicStatus.CONFIRMED


def test_explicit_no_experience_not_confirmed() -> None:
    """Шаг 2: явное «нет опыта» -> not_confirmed."""
    status = resolve_topic_status(
        signals=TopicSignals(
            correctness=False,
            example=False,
            personal_contribution=False,
        ),
        confidence=Confidence.HIGH,
        no_experience=True,
    )
    assert status == TopicStatus.NOT_CONFIRMED


def test_medium_confidence_needs_check() -> None:
    """Шаг 3: средняя уверенность -> needs_check."""
    status = resolve_topic_status(
        signals=TopicSignals(
            correctness=True,
            example=True,
            personal_contribution=True,
        ),
        confidence=Confidence.MEDIUM,
    )
    assert status == TopicStatus.NEEDS_CHECK


@pytest.mark.parametrize(
    ("confidence",),
    [(Confidence.LOW,), (Confidence.MEDIUM,)],
)
def test_low_or_medium_confidence_defaults_to_needs_check(
    confidence: Confidence,
) -> None:
    """Low/medium confidence -> needs_check even with all signals true."""
    status = resolve_topic_status(
        signals=TopicSignals(
            correctness=True,
            example=True,
            personal_contribution=True,
        ),
        confidence=confidence,
    )
    assert status == TopicStatus.NEEDS_CHECK


def test_question_skipped_not_confirmed() -> None:
    """Явный пропуск вопроса -> not_confirmed."""
    status = resolve_topic_status(
        signals=TopicSignals(
            correctness=True,
            example=True,
            personal_contribution=True,
        ),
        confidence=Confidence.HIGH,
        question_skipped=True,
    )
    assert status == TopicStatus.NOT_CONFIRMED


def test_substantial_error_high_confidence_not_confirmed() -> None:
    """Substantial technical error (correctness=False) + high -> not_confirmed."""
    status = resolve_topic_status(
        signals=TopicSignals(
            correctness=False,
            example=True,
            personal_contribution=True,
        ),
        confidence=Confidence.HIGH,
    )
    assert status == TopicStatus.NOT_CONFIRMED


@pytest.mark.parametrize(
    ("signals",),
    [
        (
            TopicSignals(
                correctness=True,
                example=False,
                personal_contribution=True,
            ),
        ),
        (
            TopicSignals(
                correctness=True,
                example=True,
                personal_contribution=False,
            ),
        ),
        (
            TopicSignals(
                correctness=True,
                example=False,
                personal_contribution=False,
            ),
        ),
    ],
)
def test_missing_example_or_contribution_high_needs_check(
    signals: TopicSignals,
) -> None:
    """Technically correct but missing example/contribution -> needs_check."""
    status = resolve_topic_status(signals=signals, confidence=Confidence.HIGH)
    assert status == TopicStatus.NEEDS_CHECK


def test_skip_beats_positive_signals() -> None:
    """Conscious skip overrides otherwise confirmable signals."""
    status = resolve_topic_status(
        signals=TopicSignals(
            correctness=True,
            example=True,
            personal_contribution=True,
        ),
        confidence=Confidence.HIGH,
        question_skipped=True,
        no_experience=False,
    )
    assert status == TopicStatus.NOT_CONFIRMED


def test_no_experience_beats_confidence() -> None:
    """Explicit no experience is not_confirmed regardless of confidence."""
    status = resolve_topic_status(
        signals=TopicSignals(
            correctness=False,
            example=False,
            personal_contribution=False,
        ),
        confidence=Confidence.LOW,
        no_experience=True,
    )
    assert status == TopicStatus.NOT_CONFIRMED


def test_error_with_medium_confidence_needs_check() -> None:
    """Incorrect answer without high confidence stays needs_check (default)."""
    status = resolve_topic_status(
        signals=TopicSignals(
            correctness=False,
            example=False,
            personal_contribution=False,
        ),
        confidence=Confidence.MEDIUM,
    )
    assert status == TopicStatus.NEEDS_CHECK
