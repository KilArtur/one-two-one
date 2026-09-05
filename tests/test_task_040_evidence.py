"""Изоляция evidence, выдача медиа и аудит реального воспроизведения."""

import uuid
from typing import Any

import pytest
from sqlalchemy import select
from test_task_026_interview_link_api import ApiFixture, _headers, api

from app.config import get_settings
from app.integrations.storage import S3StorageClient
from app.models import (
    Answer,
    AssessmentConfidence,
    AssessmentStatus,
    Candidate,
    Question,
    QuestionPattern,
    QuestionType,
    SkillType,
    Topic,
    TopicAssessment,
    TopicImportance,
    VideoViewLog,
)
from app.services.auth import AppRole

__all__ = ["api"]


async def seed(api: ApiFixture) -> tuple[uuid.UUID, uuid.UUID]:
    _, sessions, candidate_id = api
    async with sessions() as s:
        candidate = await s.get(Candidate, candidate_id)
        topic = Topic(
            vacancy_id=candidate.vacancy_id,
            title="Python",
            skill_type=SkillType.HARD,
            importance=TopicImportance.MANDATORY,
            order=0,
        )
        s.add(topic)
        await s.flush()
        q = Question(
            topic_id=topic.id,
            text="Ваш опыт?",
            type=QuestionType.CORE,
            pattern=QuestionPattern.EXPERIENCE,
        )
        s.add(q)
        await s.flush()
        answer = Answer(
            candidate_id=candidate_id,
            question_id=q.id,
            duration_sec=30,
            video_url=f"s3://{get_settings().s3_bucket}/video.webm",
            audio_url=f"s3://{get_settings().s3_bucket}/audio.webm",
        )
        assessment = TopicAssessment(
            candidate_id=candidate_id,
            topic_id=topic.id,
            system_status=AssessmentStatus.CONFIRMED,
            current_status=AssessmentStatus.CONFIRMED,
            confidence=AssessmentConfidence.HIGH,
            evidence=[
                {
                    "quote": "Я использовал Python",
                    "question_id": str(q.id),
                    "start_sec": 12,
                    "end_sec": 16,
                },
                {"quote": "Чужая цитата", "question_id": str(uuid.uuid4()), "start_sec": 0},
            ],
        )
        s.add_all([answer, assessment])
        await s.commit()
        return topic.id, answer.id


@pytest.mark.anyio
@pytest.mark.parametrize("role", list(AppRole))
async def test_evidence_playback_and_audit(
    api: ApiFixture, monkeypatch: pytest.MonkeyPatch, role: AppRole
) -> None:
    client, sessions, candidate = api
    topic, answer = await seed(api)
    client.headers.update(_headers(role))
    calls = []

    async def sign(self: S3StorageClient, key: str, **kwargs: Any) -> str:
        calls.append((key, kwargs))
        return f"https://media.test/{key}"

    monkeypatch.setattr(S3StorageClient, "generate_presigned_get_url", sign)
    base = f"/candidates/{candidate}"
    evidence = (await client.get(f"{base}/topics/{topic}/evidence")).json()
    assert len(evidence) == 1
    assert evidence[0]["start_sec"] == 12 and evidence[0]["video_available"]
    assert evidence[0]["quote"] == "Я использовал Python"
    media = await client.get(f"{base}/answers/{answer}/media")
    assert media.status_code == 200 and len(calls) == 2
    assert all(item[1]["expires_in"] == 300 for item in calls)
    assert (await client.get(f"{base}/video-views")).json() == []
    event = {"event_id": str(uuid.uuid4()), "position_sec": 12}
    for _ in range(2):
        assert (await client.post(f"{base}/answers/{answer}/views", json=event)).status_code == 200
    audit = (await client.get(f"{base}/video-views")).json()
    assert len(audit) == 1
    assert audit[0]["viewer"] == "test" and audit[0]["role"] == role.value
    assert audit[0]["position_sec"] == 12 and audit[0]["created_at"]
    async with sessions() as s:
        assert await s.scalar(select(VideoViewLog.id)) == uuid.UUID(event["event_id"])


@pytest.mark.anyio
async def test_media_and_audit_require_internal_auth_and_candidate_ownership(
    api: ApiFixture,
) -> None:
    client, sessions, candidate = api
    topic, answer = await seed(api)
    foreign = uuid.uuid4()
    paths = [
        f"/candidates/{foreign}/answers/{answer}/media",
        f"/candidates/{foreign}/topics/{topic}/evidence",
    ]
    for path in paths:
        assert (await client.get(path)).status_code == 404
    base = f"/candidates/{candidate}/answers/{answer}"
    assert (
        await client.post(f"{base}/views", json={"event_id": str(uuid.uuid4()), "position_sec": 40})
    ).status_code == 422
    async with sessions() as s:
        row = await s.get(Answer, answer)
        row.video_url = None
        await s.commit()
    assert (await client.get(f"{base}/media")).status_code == 404
    assert (
        await client.post(f"{base}/views", json={"event_id": str(uuid.uuid4()), "position_sec": 0})
    ).status_code == 404
    client.headers.clear()
    assert (await client.get(f"/candidates/{candidate}/topics/{topic}/evidence")).status_code == 401
    assert (await client.get(f"/candidates/{candidate}/video-views")).status_code == 401
