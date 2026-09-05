"""Приём чанков, идемпотентность и изоляция записи ответа (TASK-032)."""

import uuid
from typing import Any

import pytest
from sqlalchemy import func, select
from test_task_026_interview_link_api import ApiFixture, api
from test_task_030_interview import prepare

from app.integrations.storage import S3Object, S3StorageClient, S3StorageError
from app.models.answer import Answer, AnswerProcessingStatus
from app.models.answer_upload import AnswerUpload
from app.models.candidate import Candidate

__all__ = ["api"]


@pytest.fixture
async def recording(api: ApiFixture, monkeypatch: pytest.MonkeyPatch) -> tuple[Any, ...]:
    client, sessions, candidate_id = api
    own, foreign = await prepare(api)
    objects: dict[str, bytes] = {}

    async def put(
        self: S3StorageClient, key: str, data: bytes, *, content_type: str = ""
    ) -> S3Object:
        objects[key] = data
        return S3Object("test", key)

    async def compose(
        self: S3StorageClient, keys: list[str], target: str, content_type: str
    ) -> S3Object:
        objects[target] = b"".join(objects[key] for key in keys)
        return S3Object("test", target)

    monkeypatch.setattr(S3StorageClient, "put_object", put)
    monkeypatch.setattr(S3StorageClient, "compose_objects", compose)
    upload_id = str(uuid.uuid4())
    response = await client.post(
        f"/candidate-interview/questions/{own}/uploads", json={"upload_id": upload_id}
    )
    assert response.status_code == 200
    return client, sessions, candidate_id, own, foreign, upload_id, objects


async def send(client: Any, upload: str, kind: str, index: int, data: bytes = b"part") -> Any:
    return await client.put(
        f"/candidate-interview/uploads/{upload}/{kind}/{index}",
        files={"file": ("part.webm", data, f"{kind}/webm")},
    )


@pytest.mark.anyio
async def test_three_chunks_build_separate_objects_and_recorded_answer(
    recording: tuple[Any, ...],
) -> None:
    client, sessions, candidate_id, own, _, upload, objects = recording
    for kind in ("video", "audio"):
        for index in range(3):
            assert (
                await send(client, upload, kind, index, f"{kind}{index}".encode())
            ).status_code == 200
    async with sessions() as session:
        assert await session.get(Answer, uuid.UUID(upload)) is None
    payload = {"video_chunks": 3, "audio_chunks": 3, "duration_sec": 3}
    result = await client.post(f"/candidate-interview/uploads/{upload}/complete", json=payload)
    assert result.status_code == 200
    assert result.json()["processing_status"] == "recorded"
    async with sessions() as session:
        answer = await session.get(Answer, uuid.UUID(upload))
        assert answer.candidate_id == candidate_id and answer.question_id == own
        assert answer.duration_sec == 3
        assert answer.processing_status == AnswerProcessingStatus.RECORDED
        assert objects[answer.video_url.removeprefix("s3://test/")] == b"video0video1video2"
        assert objects[answer.audio_url.removeprefix("s3://test/")] == b"audio0audio1audio2"
    repeated = await client.post(f"/candidate-interview/uploads/{upload}/complete", json=payload)
    assert repeated.json() == result.json()
    async with sessions() as session:
        assert await session.scalar(select(func.count()).select_from(Answer)) == 1
    assert (await send(client, upload, "video", 3)).status_code == 409


@pytest.mark.anyio
async def test_order_and_duplicate_chunks(recording: tuple[Any, ...]) -> None:
    client, _, _, _, _, upload, objects = recording
    assert (await send(client, upload, "video", 1)).status_code == 409
    assert (await send(client, upload, "video", 0)).status_code == 200
    assert (await send(client, upload, "video", 0)).status_code == 200
    assert len(objects) == 1
    assert (await send(client, upload, "video", 0, b"changed")).status_code == 409
    response = await client.post(
        f"/candidate-interview/uploads/{upload}/complete",
        json={"video_chunks": 1, "audio_chunks": 1, "duration_sec": 3},
    )
    assert response.status_code == 409


@pytest.mark.anyio
async def test_storage_failure_does_not_create_answer_and_is_retryable(
    recording: tuple[Any, ...], monkeypatch: pytest.MonkeyPatch
) -> None:
    client, sessions, _, _, _, upload, _ = recording
    await send(client, upload, "video", 0)
    await send(client, upload, "audio", 0)
    original = S3StorageClient.compose_objects

    async def fail(
        self: S3StorageClient, keys: list[str], target: str, content_type: str
    ) -> S3Object:
        raise S3StorageError("Unavailable", "test", target)

    monkeypatch.setattr(S3StorageClient, "compose_objects", fail)
    payload = {"video_chunks": 1, "audio_chunks": 1, "duration_sec": 3}
    assert (
        await client.post(f"/candidate-interview/uploads/{upload}/complete", json=payload)
    ).status_code == 503
    async with sessions() as session:
        assert await session.get(Answer, uuid.UUID(upload)) is None
    monkeypatch.setattr(S3StorageClient, "compose_objects", original)
    assert (
        await client.post(f"/candidate-interview/uploads/{upload}/complete", json=payload)
    ).status_code == 200


@pytest.mark.anyio
async def test_new_session_picks_up_empty_upload_but_never_started_one(
    recording: tuple[Any, ...],
) -> None:
    client, _, _, own, _, upload, _ = recording
    start = f"/candidate-interview/questions/{own}/uploads"

    reused = await client.post(start, json={"upload_id": str(uuid.uuid4())})
    assert reused.status_code == 200
    assert reused.json()["id"] == upload

    assert (await send(client, upload, "video", 0)).status_code == 200
    blocked = await client.post(start, json={"upload_id": str(uuid.uuid4())})
    assert blocked.status_code == 409


@pytest.mark.anyio
async def test_upload_is_scoped_to_candidate_and_consent(recording: tuple[Any, ...]) -> None:
    client, sessions, candidate_id, own, foreign, upload, _ = recording
    assert (
        await client.post(
            f"/candidate-interview/questions/{foreign}/uploads",
            json={"upload_id": str(uuid.uuid4())},
        )
    ).status_code == 404
    assert (await send(client, str(uuid.uuid4()), "video", 0)).status_code == 404
    async with sessions() as session:
        row = await session.get(AnswerUpload, uuid.UUID(upload))
        candidate = await session.get(Candidate, candidate_id)
        other = Candidate(vacancy_id=candidate.vacancy_id)
        session.add(other)
        await session.flush()
        row.candidate_id = other.id
        await session.commit()
    assert (await send(client, upload, "video", 0)).status_code == 404
    async with sessions() as session:
        candidate = await session.get(Candidate, candidate_id)
        candidate.consent_given_at = None
        await session.commit()
    assert (
        await client.post(
            f"/candidate-interview/questions/{own}/uploads", json={"upload_id": upload}
        )
    ).status_code == 403


@pytest.mark.anyio
async def test_limits_and_mime(recording: tuple[Any, ...]) -> None:
    client, _, _, _, _, upload, _ = recording
    assert (await send(client, upload, "video", 0, b"")).status_code == 413
    assert (await send(client, upload, "video", 300)).status_code == 422
    response = await client.put(
        f"/candidate-interview/uploads/{upload}/audio/0",
        files={"file": ("bad", b"bad", "video/webm")},
    )
    assert response.status_code == 415
    response = await client.post(
        f"/candidate-interview/uploads/{upload}/complete",
        json={"video_chunks": 1, "audio_chunks": 1, "duration_sec": 121},
    )
    assert response.status_code == 422
