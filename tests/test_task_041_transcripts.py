"""Выдача полного транскрипта и изоляция цитат по кандидату/вопросу/топику."""

import uuid

import pytest
from sqlalchemy import select
from test_task_026_interview_link_api import ApiFixture, _headers, api
from test_task_040_evidence import seed

from app.models import Answer, Candidate, TopicAssessment
from app.services.auth import AppRole

__all__ = ["api"]


@pytest.mark.anyio
@pytest.mark.parametrize("role", list(AppRole))
async def test_full_transcript_segments_and_quotes(api: ApiFixture, role: AppRole) -> None:
    client, sessions, candidate_id = api
    topic, answer_id = await seed(api)
    async with sessions() as s:
        answer = await s.get(Answer, answer_id)
        answer.transcript = "В начале. Я использовал Python в сервисе."
        answer.transcript_segments = [
            {"text": "В начале.", "start": 0, "end": 2},
            {"text": "Я использовал", "start": 2, "end": 4},
            {"text": "Python в сервисе.", "start": 4, "end": 7},
        ]
        candidate = await s.get(Candidate, candidate_id)
        candidate.resume_text = "Заявлено: 10 лет опыта"
        await s.commit()
    client.headers.update(_headers(role))
    response = await client.get(f"/candidates/{candidate_id}/transcript")
    assert response.status_code == 200
    (item,) = response.json()
    assert item["transcript"] == "В начале. Я использовал Python в сервисе."
    assert [seg["start"] for seg in item["segments"]] == [0, 2, 4]
    assert item["quotes"] == ["Я использовал Python"]
    assert "resume" not in response.text and "10 лет опыта" not in response.text
    assert (await client.get(f"/candidates/{candidate_id}/transcript?topic_id={topic}")).json() == [
        item
    ]
    assert (
        await client.get(f"/candidates/{candidate_id}/transcript?topic_id={uuid.uuid4()}")
    ).status_code == 404


@pytest.mark.anyio
async def test_missing_and_purged_transcripts_do_not_leak_quotes(api: ApiFixture) -> None:
    client, sessions, candidate_id = api
    _, answer_id = await seed(api)
    async with sessions() as s:
        answer = await s.get(Answer, answer_id)
        answer.technically_lost = True
        answer.skipped = True
        answer.processing_status = "error"
        await s.commit()
    (item,) = (await client.get(f"/candidates/{candidate_id}/transcript")).json()
    assert item["segments"] == item["quotes"] == []
    assert item["transcript"] is None
    assert item["skipped"] and item["technically_lost"] and item["processing_status"] == "error"
    assert (await client.get(f"/candidates/{uuid.uuid4()}/transcript")).status_code == 404
    client.headers.clear()
    assert (await client.get(f"/candidates/{candidate_id}/transcript")).status_code == 401


@pytest.mark.anyio
async def test_foreign_candidate_and_foreign_topic_quotes_are_excluded(api: ApiFixture) -> None:
    client, sessions, candidate_id = api
    topic_id, answer_id = await seed(api)
    async with sessions() as s:
        answer = await s.get(Answer, answer_id)
        answer.transcript = "Я использовал Python"
        owner = await s.get(Candidate, candidate_id)
        other = Candidate(vacancy_id=owner.vacancy_id)
        s.add(other)
        await s.flush()
        s.add(
            Answer(candidate_id=other.id, question_id=answer.question_id, transcript="Чужой ответ")
        )
        assessment = await s.scalar(
            select(TopicAssessment).where(TopicAssessment.topic_id == topic_id)
        )
        assessment.evidence = [
            *assessment.evidence,
            {"quote": "Чужое", "question_id": str(uuid.uuid4())},
        ]
        await s.commit()
    (item,) = (await client.get(f"/candidates/{candidate_id}/transcript")).json()
    assert item["quotes"] == ["Я использовал Python"]
    assert item["transcript"] == "Я использовал Python"
