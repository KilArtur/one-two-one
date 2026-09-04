"""Детерминированное правило статуса топика Р13 (TASK-015)."""

from app.models.topic_assessment import AssessmentConfidence, AssessmentStatus
from app.services.topic_status import TopicSignals, resolve_topic_status


def test_three_signals_high_confidence_confirmed() -> None:
    status = resolve_topic_status(
        signals=TopicSignals(correctness=True, example=True, personal_contribution=True),
        confidence=AssessmentConfidence.HIGH,
    )
    assert status == AssessmentStatus.CONFIRMED


def test_explicit_no_experience_not_confirmed() -> None:
    status = resolve_topic_status(
        signals=TopicSignals(),
        confidence=AssessmentConfidence.HIGH,
        explicit_no_experience=True,
    )
    assert status == AssessmentStatus.NOT_CONFIRMED


def test_technical_error_high_confidence_not_confirmed() -> None:
    status = resolve_topic_status(
        signals=TopicSignals(correctness=False, example=True, personal_contribution=True),
        confidence=AssessmentConfidence.HIGH,
        technical_error=True,
    )
    assert status == AssessmentStatus.NOT_CONFIRMED


def test_skipped_question_not_confirmed_even_with_signals() -> None:
    status = resolve_topic_status(
        signals=TopicSignals(correctness=True, example=True, personal_contribution=True),
        confidence=AssessmentConfidence.HIGH,
        skipped=True,
    )
    assert status == AssessmentStatus.NOT_CONFIRMED


def test_medium_confidence_needs_check() -> None:
    status = resolve_topic_status(
        signals=TopicSignals(correctness=True, example=True, personal_contribution=True),
        confidence=AssessmentConfidence.MEDIUM,
    )
    assert status == AssessmentStatus.NEEDS_CHECK


def test_low_confidence_needs_check() -> None:
    status = resolve_topic_status(
        signals=TopicSignals(correctness=True, example=True, personal_contribution=True),
        confidence=AssessmentConfidence.LOW,
    )
    assert status == AssessmentStatus.NEEDS_CHECK


def test_high_confidence_missing_signal_needs_check() -> None:
    status = resolve_topic_status(
        signals=TopicSignals(correctness=True, example=False, personal_contribution=True),
        confidence=AssessmentConfidence.HIGH,
    )
    assert status == AssessmentStatus.NEEDS_CHECK


def test_no_experience_at_medium_confidence_defaults_to_needs_check() -> None:
    status = resolve_topic_status(
        signals=TopicSignals(),
        confidence=AssessmentConfidence.MEDIUM,
        explicit_no_experience=True,
    )
    assert status == AssessmentStatus.NEEDS_CHECK


def test_signals_from_mapping() -> None:
    signals = TopicSignals.from_mapping({"correctness": True, "example": True})
    assert signals.correctness is True
    assert signals.example is True
    assert signals.personal_contribution is False
    assert TopicSignals.from_mapping(None).all_present is False
