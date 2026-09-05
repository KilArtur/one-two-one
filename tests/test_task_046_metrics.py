"""Доли статусов, итог ревью и completion rate без повторного учёта объектов."""

import uuid

import pytest
from sqlalchemy import select
from test_task_026_interview_link_api import ApiFixture, _headers, api
from test_task_040_evidence import seed

from app.models import Answer, Candidate, CandidateStatus, TopicAssessment
from app.services.auth import AppRole
from app.services.product_metrics import InterviewSnapshot, TopicSnapshot, compute_metrics

__all__ = ["api"]


def test_empty_and_out_of_scope_do_not_invent_percentages() -> None:
    data = compute_metrics([TopicSnapshot("out_of_scope", "out_of_scope", False)], [])
    assert data.completion.share is None
    assert data.changed_after_review.share is None
    assert all(v.total == 0 and v.share is None for v in data.current_statuses.values())


def test_net_review_directions_and_distinct_interview_denominator() -> None:
    topics = [
        TopicSnapshot("needs_check", "confirmed", True),
        TopicSnapshot("confirmed", "not_confirmed", True),
        TopicSnapshot("needs_check", "needs_check", True),
        TopicSnapshot("needs_check", "needs_check", False),
    ]
    data = compute_metrics(
        topics,
        [
            InterviewSnapshot(True, True, False),
            InterviewSnapshot(True, False, True),
            InterviewSnapshot(False, False, False),
        ],
    )
    assert data.reviewed_topics == 3
    assert data.changed_after_review.count == 2
    assert data.changed_after_review.share == 2 / 3
    assert data.disputed_changed_after_review.share == 1 / 3
    assert data.system_statuses["needs_check"].count == 3
    assert data.current_statuses["needs_check"].count == 2
    assert {(d.from_status, d.to_status, d.count) for d in data.review_directions} == {
        ("needs_check", "confirmed", 1),
        ("confirmed", "not_confirmed", 1),
    }
    assert data.completion.share == data.technical_failures.share == 0.5


@pytest.mark.anyio
async def test_metrics_refresh_after_real_review_and_interruption(api: ApiFixture) -> None:
    client, sessions, candidate_id = api
    _, answer_id = await seed(api)
    async with sessions() as s:
        candidate = await s.get(Candidate, candidate_id)
        candidate.status = CandidateStatus.PROCESSED
        vacancy_id = candidate.vacancy_id
        assessment = await s.scalar(
            select(TopicAssessment).where(TopicAssessment.candidate_id == candidate_id)
        )
        assessment.system_status = assessment.current_status = "needs_check"
        assessment_id = assessment.id
        s.add(Candidate(vacancy_id=vacancy_id))
        await s.commit()
    path = f"/metrics/product?vacancy_id={vacancy_id}"
    initial = (await client.get(path)).json()
    assert initial["completion"] == {"count": 1, "total": 1, "share": 1.0}
    assert initial["reviewed_topics"] == 0
    client.headers.update(_headers(AppRole.TECH_SPECIALIST))
    for new in ["confirmed", "needs_check", "confirmed"]:
        response = await client.patch(
            f"/topic-assessments/{assessment_id}/status",
            json={"new_status": new, "comment": "Проверил фрагмент"},
        )
        assert response.status_code == 200
    data = (await client.get(path)).json()
    assert data["reviewed_topics"] == 1
    assert data["changed_after_review"] == {"count": 1, "total": 1, "share": 1.0}
    assert data["review_directions"] == [
        {"from_status": "needs_check", "to_status": "confirmed", "count": 1}
    ]
    assert data["system_statuses"]["needs_check"]["count"] == 1
    assert data["current_statuses"]["confirmed"]["count"] == 1
    async with sessions() as s:
        original = await s.get(Answer, answer_id)
        interrupted = Candidate(vacancy_id=vacancy_id, status=CandidateStatus.IN_PROGRESS)
        s.add(interrupted)
        await s.flush()
        s.add(
            Answer(
                candidate_id=interrupted.id, question_id=original.question_id, technically_lost=True
            )
        )
        await s.commit()
    data = (await client.get(path)).json()
    assert data["completion"] == {"count": 1, "total": 2, "share": 0.5}
    assert data["technical_failures"] == {"count": 1, "total": 2, "share": 0.5}
    empty = (await client.get(f"/metrics/product?vacancy_id={uuid.uuid4()}")).json()
    assert empty["completion"]["share"] is None
    client.headers.clear()
    assert (await client.get(path)).status_code == 401


@pytest.mark.anyio
@pytest.mark.parametrize("role", list(AppRole))
async def test_metrics_available_to_internal_roles(api: ApiFixture, role: AppRole) -> None:
    client, _, _ = api
    client.headers.update(_headers(role))
    assert (await client.get("/metrics/product")).status_code == 200
