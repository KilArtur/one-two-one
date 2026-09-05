"""Доступ кандидата к вопросам и потоковой озвучке (TASK-030)."""

import uuid
from collections.abc import AsyncGenerator

import pytest
from sqlalchemy import select
from test_task_026_interview_link_api import ApiFixture, api

from app.models.candidate import Candidate
from app.models.question import Question, QuestionPattern, QuestionType
from app.models.topic import SkillType, Topic, TopicImportance
from app.models.vacancy import Vacancy, VacancyGrade

__all__ = ["api"]


async def prepare(api: ApiFixture) -> tuple[uuid.UUID, uuid.UUID]:
    """Возвращает id своего вопроса кандидата и вопроса чужой вакансии."""
    client, sessions, candidate_id = api
    async with sessions() as session:
        candidate = await session.get(Candidate, candidate_id)
        own = await session.scalar(
            select(Question.id)
            .join(Topic, Question.topic_id == Topic.id)
            .where(Topic.vacancy_id == candidate.vacancy_id)
        )
        other = Vacancy(title="Other", grade=VacancyGrade.MIDDLE)
        session.add(other)
        await session.flush()
        topic = Topic(
            vacancy_id=other.id,
            title="Python",
            skill_type=SkillType.HARD,
            importance=TopicImportance.MANDATORY,
            order=0,
        )
        session.add(topic)
        await session.flush()
        foreign = Question(
            topic_id=topic.id,
            text="Расскажите о Python",
            type=QuestionType.CORE,
            pattern=QuestionPattern.EXPERIENCE,
            source_reason="internal reason",
            reviewed_by_expert=True,
        )
        session.add(foreign)
        await session.commit()
        foreign_id = foreign.id
    link = (await client.post(f"/candidates/{candidate_id}/interview-link")).json()
    exchanged = await client.post("/candidate-auth/exchange", json={"token": link["token"]})
    client.headers["Authorization"] = f"Bearer {exchanged.json()['access_token']}"
    return own, foreign_id


@pytest.mark.anyio
async def test_only_own_core_questions_are_visible(api: ApiFixture) -> None:
    client, sessions, _ = api
    own, foreign = await prepare(api)
    response = await client.get("/candidate-interview/questions")
    assert response.status_code == 200
    payload = response.json()
    assert len(payload) == 1
    item = payload[0]
    assert item["id"] == str(own)
    assert item["type"] == "core"
    assert item["text"] == "Расскажите о Python"
    assert "topic_id" in item
    assert (await client.get(f"/candidate-interview/questions/{foreign}/audio")).status_code == 404
    async with sessions() as session:
        question = await session.get(Question, own)
        question.type = QuestionType.PERSONAL
        await session.commit()
    assert (await client.get("/candidate-interview/questions")).json() == []
    assert (await client.get(f"/candidate-interview/questions/{own}/audio")).status_code == 404


@pytest.mark.anyio
async def test_consent_required(api: ApiFixture) -> None:
    client, sessions, candidate_id = api
    own, _ = await prepare(api)
    async with sessions() as session:
        candidate = await session.get(Candidate, candidate_id)
        candidate.consent_given_at = None
        await session.commit()
    assert (await client.get("/candidate-interview/questions")).status_code == 403
    assert (await client.get(f"/candidate-interview/questions/{own}/audio")).status_code == 403
    client.headers.clear()
    assert (await client.get("/candidate-interview/questions")).status_code == 401


@pytest.mark.anyio
async def test_audio_stream_and_typed_error(
    api: ApiFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.integrations.tts import TTSClientError
    from app.services.question_audio import QuestionAudioService

    client, _, _ = api
    own, _ = await prepare(api)

    async def stream(self: QuestionAudioService, question: Question) -> AsyncGenerator[bytes, None]:
        yield b"mp3-first"
        yield b"-last"

    monkeypatch.setattr(QuestionAudioService, "stream_audio", stream)
    response = await client.get(f"/candidate-interview/questions/{own}/audio")
    assert response.status_code == 200
    assert response.content == b"mp3-first-last"
    assert response.headers["content-type"] == "audio/mpeg"

    async def fail(self: QuestionAudioService, question: Question) -> AsyncGenerator[bytes, None]:
        raise TTSClientError("unavailable")
        yield b""

    monkeypatch.setattr(QuestionAudioService, "stream_audio", fail)
    assert (await client.get(f"/candidate-interview/questions/{own}/audio")).status_code == 503
