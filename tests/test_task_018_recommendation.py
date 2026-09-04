"""Детерминированная итоговая рекомендация Р5 (TASK-018)."""

from app.models.interview_result import InterviewRecommendation
from app.models.topic import TopicImportance
from app.models.topic_assessment import AssessmentStatus
from app.services.matrix import TopicOutcome
from app.services.recommendation import compute_recommendation

M = TopicImportance.MANDATORY
D = TopicImportance.DESIRED
CONFIRMED = AssessmentStatus.CONFIRMED
NEEDS = AssessmentStatus.NEEDS_CHECK
NOT_CONF = AssessmentStatus.NOT_CONFIRMED
OOS = AssessmentStatus.OUT_OF_SCOPE


def test_mandatory_not_confirmed_gives_not_fit() -> None:
    outcomes = [
        TopicOutcome(M, CONFIRMED),
        TopicOutcome(M, NOT_CONF),
        TopicOutcome(M, CONFIRMED),
    ]
    assert compute_recommendation(outcomes) == InterviewRecommendation.NOT_FIT


def test_one_mandatory_needs_check_gives_additional_check() -> None:
    outcomes = [
        TopicOutcome(M, CONFIRMED),
        TopicOutcome(M, NEEDS),
        TopicOutcome(M, CONFIRMED),
    ]
    assert compute_recommendation(outcomes) == InterviewRecommendation.ADDITIONAL_CHECK


def test_all_mandatory_confirmed_gives_fit() -> None:
    outcomes = [TopicOutcome(M, CONFIRMED), TopicOutcome(M, CONFIRMED)]
    assert compute_recommendation(outcomes) == InterviewRecommendation.FIT


def test_stop_factor_forces_not_fit() -> None:
    outcomes = [TopicOutcome(M, CONFIRMED), TopicOutcome(M, CONFIRMED)]
    assert (
        compute_recommendation(outcomes, stop_factor_triggered=True)
        == InterviewRecommendation.NOT_FIT
    )


def test_not_confirmed_takes_priority_over_needs_check() -> None:
    outcomes = [TopicOutcome(M, NEEDS), TopicOutcome(M, NOT_CONF)]
    assert compute_recommendation(outcomes) == InterviewRecommendation.NOT_FIT


def test_out_of_scope_excluded_from_calculation() -> None:
    # единственный «плохой» обязательный топик вне зоны интервью — не влияет
    outcomes = [TopicOutcome(M, CONFIRMED), TopicOutcome(M, OOS)]
    assert compute_recommendation(outcomes) == InterviewRecommendation.FIT


def test_desired_topics_do_not_affect_recommendation() -> None:
    # желательные not_confirmed/needs_check не меняют рекомендацию
    outcomes = [
        TopicOutcome(M, CONFIRMED),
        TopicOutcome(D, NOT_CONF),
        TopicOutcome(D, NEEDS),
    ]
    assert compute_recommendation(outcomes) == InterviewRecommendation.FIT


def test_no_llm_pure_function() -> None:
    # чистая функция: одинаковый вход -> одинаковый результат, без побочных эффектов
    outcomes = [TopicOutcome(M, NEEDS)]
    first = compute_recommendation(outcomes)
    second = compute_recommendation(outcomes)
    assert first == second == InterviewRecommendation.ADDITIONAL_CHECK
