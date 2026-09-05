"""Verify the saved-recording to result path and reviewer permissions."""

import uuid

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db import Base, get_db
from app.integrations.asr import TranscriptionResult
from app.integrations.llm import LLMInvocationResult
from app.integrations.storage import S3Object, get_s3_storage_client
from app.main import create_app
from app.models.candidate import Candidate, CandidateStatus
from app.models.topic_assessment import TopicAssessment
from app.schemas.assessment import TopicAssessmentLLM
from app.services import pipeline, transcription
from app.services.auth import AppRole, create_access_token
from app.services.evidence import locate_evidence
from app.tasks import local_pipeline


class Storage:
    def __init__(self):
        self.objects = {}

    async def put_object(self, key, data, **kwargs):
        self.objects[key] = data

    async def get_object_bytes(self, key):
        return self.objects[key]

    async def compose_objects(self, keys, target, content_type):
        self.objects[target] = b"".join(self.objects[key] for key in keys)
        return S3Object("test", target)


class ASR:
    async def transcribe(self, audio, **kwargs):
        return TranscriptionResult(
            "Я использовал async await",
            [{"text": "Я использовал async await", "start": 1, "end": 4}],
            "test-asr",
        )


class LLM:
    async def generate_structured(self, prompt, **kwargs):
        return LLMInvocationResult(
            TopicAssessmentLLM(
                correctness=True,
                example=False,
                personal_contribution=True,
                confidence="medium",
                explicit_no_experience=False,
                technical_error=False,
                evidence_quote="Я использовал async await",
                reasoning_summary="Нужен пример",
            ),
            "test-model",
            "test-prompt",
        )


@pytest.mark.anyio
async def test_invite_record_submit_process_review(monkeypatch):
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    maker = async_sessionmaker(engine, expire_on_commit=False)
    settings = Settings(_env_file=None, jwt_secret_key="test", app_env="testing")
    app = create_app(settings)
    storage = Storage()

    async def db():
        async with maker() as session:
            yield session

    async def dispose():
        pass

    app.dependency_overrides[get_db] = db
    app.dependency_overrides[get_s3_storage_client] = lambda: storage
    monkeypatch.setattr(local_pipeline, "get_sessionmaker", lambda: maker)
    monkeypatch.setattr(local_pipeline, "dispose_engine", dispose)
    for module in (pipeline, transcription):
        monkeypatch.setattr(module, "get_asr_client", ASR)
        monkeypatch.setattr(module, "get_s3_storage_client", lambda: storage)
    monkeypatch.setattr(pipeline, "get_llm_client", LLM)
    headers = {
        "Authorization": "Bearer "
        + create_access_token(
            username="recruiter",
            role=AppRole.RECRUITER,
            settings=settings,
        )
    }
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as api:
        v = (
            await api.post(
                "/vacancies",
                json={
                    "title": "Test",
                    "grade": "middle",
                    "topics": [
                        {"title": "Python", "skill_type": "hard", "importance": "mandatory"},
                    ],
                },
            )
        ).json()
        from app.models.question import Question, QuestionPattern, QuestionType

        async with maker() as session:
            question = Question(
                topic_id=uuid.UUID(v["topics"][0]["id"]),
                text="Опыт?",
                type=QuestionType.CORE,
                pattern=QuestionPattern.EXPERIENCE,
                reviewed_by_expert=True,
            )
            session.add(question)
            await session.commit()
            question_id = str(question.id)
        created = await api.post("/candidates", headers=headers, json={"vacancy_id": v["id"]})
        assert created.status_code == 201
        candidate_id = created.json()["id"]
        link = (
            await api.post(f"/candidates/{candidate_id}/interview-link", headers=headers)
        ).json()
        token = (await api.post("/candidate-auth/exchange", json={"token": link["token"]})).json()
        candidate_headers = {"Authorization": "Bearer " + token["access_token"]}
        await api.post(
            "/candidate-auth/consent", json={"accepted": True}, headers=candidate_headers
        )
        upload_id = str(uuid.uuid4())
        assert (
            await api.post(
                f"/candidate-interview/questions/{question_id}/uploads",
                headers=candidate_headers,
                json={"upload_id": upload_id},
            )
        ).status_code == 200
        for kind in ("video", "audio"):
            assert (
                await api.put(
                    f"/candidate-interview/uploads/{upload_id}/{kind}/0",
                    headers=candidate_headers,
                    files={"file": ("chunk", b"x" * 1024, f"{kind}/webm")},
                )
            ).status_code == 200
        assert (
            await api.post(
                f"/candidate-interview/uploads/{upload_id}/complete",
                headers=candidate_headers,
                json={"video_chunks": 1, "audio_chunks": 1, "duration_sec": 5},
            )
        ).status_code == 200
        await local_pipeline.process_pending()
        async with maker() as session:
            assert not list(await session.scalars(select(TopicAssessment)))
        assert (
            await api.post("/candidate-auth/submit", headers=candidate_headers)
        ).status_code == 200
        assert (await local_pipeline.process_pending())["processed"] == 1
        assert (await local_pipeline.process_pending())["processed"] == 0
        async with maker() as session:
            assessment = await session.scalar(select(TopicAssessment))
            assessment_id = str(assessment.id)
            assert (
                await session.get(Candidate, uuid.UUID(candidate_id))
            ).status == CandidateStatus.PROCESSED
        result = (await api.get(f"/candidates/{candidate_id}/result", headers=headers)).json()
        assert result["needs_check_count"] == 1
        assert result["topics"][0]["has_evidence"]
        change = {"new_status": "confirmed", "comment": "Проверил запись"}
        route = f"/topic-assessments/{assessment_id}/status"
        assert (await api.patch(route, headers=headers, json=change)).status_code == 403
        tech = {
            "Authorization": "Bearer "
            + create_access_token(
                username="tech",
                role=AppRole.TECH_SPECIALIST,
                settings=settings,
            )
        }
        assert (await api.patch(route, headers=tech, json=change)).status_code == 200
        result = (await api.get(f"/candidates/{candidate_id}/result", headers=tech)).json()
        assert result["topics"][0]["system_status"] == "needs_check"
        assert result["topics"][0]["current_status"] == "confirmed"
        assert (
            await api.post("/candidate-auth/exchange", json={"token": link["token"]})
        ).status_code == 403
    await engine.dispose()


def test_evidence_rejects_invented_quote_and_preserves_actual_time():
    question_id = uuid.uuid4()
    segments = [
        {"text": "Начало", "start": 0, "end": 2},
        {"text": "Я использовал", "start": 2, "end": 4},
        {"text": "async await", "start": 4, "end": 6},
    ]
    assert locate_evidence(segments, "Я использовал Java", question_id=question_id) is None
    result = locate_evidence(segments, "Я использовал async await", question_id=question_id)
    assert (result["start_sec"], result["end_sec"]) == (2, 6)
