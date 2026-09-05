"""HTTP-контракт очереди, контекста и сохранения статуса из формы ревью."""

import pytest
from sqlalchemy import select
from test_task_026_interview_link_api import ApiFixture, _headers, api
from test_task_040_evidence import seed

from app.models import (
    Answer,
    AssessmentConfidence,
    AssessmentStatus,
    Candidate,
    SkillType,
    Topic,
    TopicAssessment,
    TopicImportance,
)
from app.services.auth import AppRole

__all__ = ["api"]


@pytest.mark.anyio
async def test_role_context_and_result_refresh(api: ApiFixture) -> None:
    client, sessions, candidate_id = api
    hard, answer_id = await seed(api)
    async with sessions() as s:
        candidate = await s.get(Candidate, candidate_id)
        answer = await s.get(Answer, answer_id)
        answer.transcript = "Я использовал Python"
        assessment = await s.scalar(select(TopicAssessment).where(TopicAssessment.topic_id == hard))
        assessment.system_status = assessment.current_status = AssessmentStatus.NEEDS_CHECK
        assessment.reasoning_summary = "Неясен личный вклад"
        hard_id = assessment.id
        topic = Topic(
            vacancy_id=candidate.vacancy_id,
            title="Коммуникация",
            skill_type=SkillType.SOFT,
            importance=TopicImportance.DESIRED,
            order=1,
        )
        s.add(topic)
        await s.flush()
        s.add(
            TopicAssessment(
                candidate_id=candidate_id,
                topic_id=topic.id,
                system_status=AssessmentStatus.NEEDS_CHECK,
                current_status=AssessmentStatus.NEEDS_CHECK,
                confidence=AssessmentConfidence.LOW,
            )
        )
        await s.commit()
    client.headers.update(_headers(AppRole.TECH_SPECIALIST))
    queue = (await client.get("/review-queue")).json()
    assert len(queue) == 1 and queue[0]["skill_type"] == "hard"
    assert queue[0]["reasoning_summary"] == "Неясен личный вклад"
    context = (await client.get(f"/candidates/{candidate_id}/transcript?topic_id={hard}")).json()
    assert context[0]["transcript"] == "Я использовал Python"
    assert context[0]["quotes"] == ["Я использовал Python"]
    path = f"/topic-assessments/{hard_id}/status"
    for comment in ["", "   ", "\n\t"]:
        assert (
            await client.patch(path, json={"new_status": "confirmed", "comment": comment})
        ).status_code == 422
    assert (
        await client.patch(path, json={"new_status": "confirmed", "comment": " Проверил видео "})
    ).status_code == 200
    assert (await client.get("/review-queue")).json() == []
    card = (await client.get(f"/candidates/{candidate_id}/result")).json()
    row = next(t for t in card["topics"] if t["topic_id"] == str(hard))
    assert row["current_status"] == "confirmed" and row["system_status"] == "needs_check"
    assert row["author"] == "technical_specialist"
    client.headers.update(_headers(AppRole.HIRING_MANAGER))
    assert {t["skill_type"] for t in (await client.get("/review-queue")).json()} == {"soft"}
    assert (
        await client.patch(path, json={"new_status": "not_confirmed", "comment": "Проверил"})
    ).status_code == 403
    client.headers.update(_headers())
    assert (await client.get("/review-queue")).status_code == 403
    assert (
        await client.patch(path, json={"new_status": "not_confirmed", "comment": "Проверил"})
    ).status_code == 403
