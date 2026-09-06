"""Расчёт Coverage Р4: тройка чисел всегда, mandatory_coverage без спорных, без AI-score."""

import dataclasses
from decimal import Decimal

from app.models.topic import TopicImportance
from app.models.topic_assessment import AssessmentStatus
from app.services.coverage import CoverageResult, compute_coverage
from app.services.matrix import TopicOutcome

M = TopicImportance.MANDATORY
D = TopicImportance.DESIRED
CONFIRMED = AssessmentStatus.CONFIRMED
NEEDS = AssessmentStatus.NEEDS_CHECK
NOT_CONF = AssessmentStatus.NOT_CONFIRMED
OOS = AssessmentStatus.OUT_OF_SCOPE


def test_triple_counts_always_with_disputed_coverage_null() -> None:
    outcomes = [
        TopicOutcome(M, CONFIRMED),
        TopicOutcome(M, CONFIRMED),
        TopicOutcome(M, NEEDS),
        TopicOutcome(M, NOT_CONF),
        TopicOutcome(D, CONFIRMED),
    ]
    result = compute_coverage(outcomes)

    # Шаг 1: тройка чисел есть, mandatory_coverage = None пока есть спорные
    assert (result.confirmed_count, result.needs_check_count, result.not_confirmed_count) == (
        3,
        1,
        1,
    )
    assert result.mandatory_coverage is None
    assert result.mandatory_confirmed_share == Decimal("0.5000")
    assert result.mandatory_potential_share == Decimal("0.7500")
    assert result.desired_confirmed_share == Decimal("1.0000")


def test_mandatory_coverage_appears_after_disputes_closed() -> None:
    # все спорные закрыты: 3 confirmed + 1 not_confirmed из 4 обязательных
    outcomes = [
        TopicOutcome(M, CONFIRMED),
        TopicOutcome(M, CONFIRMED),
        TopicOutcome(M, CONFIRMED),
        TopicOutcome(M, NOT_CONF),
    ]
    result = compute_coverage(outcomes)

    # Шаг 2: появляется дробь mandatory_coverage
    assert result.mandatory_coverage == Decimal("0.7500")


def test_out_of_scope_excluded_from_denominator() -> None:
    # 2 confirmed + 1 out_of_scope: знаменатель = 2, coverage = 1.0
    outcomes = [
        TopicOutcome(M, CONFIRMED),
        TopicOutcome(M, CONFIRMED),
        TopicOutcome(M, OOS),
    ]
    result = compute_coverage(outcomes)

    assert result.mandatory_coverage == Decimal("1.0000")
    # out_of_scope не попадает и в тройку чисел
    assert (result.confirmed_count, result.needs_check_count, result.not_confirmed_count) == (
        2,
        0,
        0,
    )


def test_desired_coverage_computed_separately() -> None:
    outcomes = [
        TopicOutcome(M, CONFIRMED),
        TopicOutcome(D, CONFIRMED),
        TopicOutcome(D, NOT_CONF),
    ]
    result = compute_coverage(outcomes)

    assert result.mandatory_coverage == Decimal("1.0000")
    assert result.desired_coverage == Decimal("0.5000")


def test_desired_coverage_null_while_disputed() -> None:
    outcomes = [TopicOutcome(D, CONFIRMED), TopicOutcome(D, NEEDS)]
    result = compute_coverage(outcomes)
    assert result.desired_coverage is None


def test_no_mandatory_topics_gives_null_coverage() -> None:
    outcomes = [TopicOutcome(D, CONFIRMED)]
    result = compute_coverage(outcomes)
    assert result.mandatory_coverage is None
    assert result.desired_coverage == Decimal("1.0000")


def test_no_aggregate_score_field_exists() -> None:
    # Шаг 3: результат не содержит единого балла/AI-score — только тройка и доли
    field_names = {field.name for field in dataclasses.fields(CoverageResult)}
    assert field_names == {
        "confirmed_count",
        "needs_check_count",
        "not_confirmed_count",
        "mandatory_coverage",
        "desired_coverage",
        "mandatory_confirmed_share",
        "desired_confirmed_share",
        "mandatory_potential_share",
    }
    assert not any("score" in name for name in field_names)
