"""Последовательная загрузка частей и атомарная фиксация записанного ответа."""

import hashlib
import uuid
from typing import Literal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.storage import S3StorageClient
from app.models.answer import Answer, AnswerProcessingStatus
from app.models.answer_upload import AnswerUpload
from app.models.candidate import Candidate, CandidateStatus
from app.models.question import Question
from app.services.candidate_questions import candidate_questions_stmt

TrackKind = Literal["video", "audio"]
MAX_CHUNK_BYTES = 8 * 1024 * 1024
MAX_ANSWER_BYTES = 256 * 1024 * 1024
MEDIA_TYPES = {
    "video": {"video/webm": "webm", "video/mp4": "mp4"},
    "audio": {"audio/webm": "webm", "audio/mp4": "mp4", "audio/ogg": "ogg"},
}


async def start_upload(
    session: AsyncSession, candidate: Candidate, question_id: uuid.UUID, upload_id: uuid.UUID
) -> AnswerUpload:
    """Выделяет одну загрузку на пару кандидат/вопрос без разрешения перезаписи."""
    await session.scalar(select(Candidate).where(Candidate.id == candidate.id).with_for_update())
    question = await session.scalar(
        candidate_questions_stmt(candidate.id, candidate.vacancy_id).where(
            Question.id == question_id
        )
    )
    if question is None:
        raise HTTPException(404, "Question not found")
    upload = await session.scalar(
        select(AnswerUpload).where(
            AnswerUpload.candidate_id == candidate.id, AnswerUpload.question_id == question_id
        )
    )
    if upload is not None and upload.id != upload_id:
        raise HTTPException(409, "Recording already started in another session")
    if upload is None:
        if await session.get(AnswerUpload, upload_id) is not None:
            raise HTTPException(409, "Upload identifier is already used")
        upload = AnswerUpload(
            id=upload_id,
            candidate_id=candidate.id,
            question_id=question_id,
            manifest={"video": {"type": "", "parts": []}, "audio": {"type": "", "parts": []}},
        )
        session.add(upload)
        candidate.status = CandidateStatus.IN_PROGRESS
        await session.commit()
        await session.refresh(upload)
    return upload


async def locked_upload(
    session: AsyncSession, candidate_id: uuid.UUID, upload_id: uuid.UUID
) -> AnswerUpload:
    upload = await session.scalar(
        select(AnswerUpload)
        .where(AnswerUpload.id == upload_id, AnswerUpload.candidate_id == candidate_id)
        .with_for_update()
    )
    if upload is None:
        raise HTTPException(404, "Upload not found")
    return upload


def part_key(upload: AnswerUpload, kind: TrackKind, index: int) -> str:
    return f"answers/{upload.candidate_id}/{upload.id}/parts/{kind}/{index:04d}"


async def put_chunk(
    session: AsyncSession,
    upload: AnswerUpload,
    storage: S3StorageClient,
    kind: TrackKind,
    index: int,
    data: bytes,
    content_type: str,
) -> None:
    """Принимает следующий чанк или идентичный повтор ранее подтверждённого."""
    if await session.get(Answer, upload.id) is not None:
        raise HTTPException(409, "Answer is already saved")
    lane = upload.manifest[kind]
    parts = lane["parts"]
    mime = content_type.split(";", 1)[0].strip().lower()
    # Финальный чанк MediaRecorder может прийти без типа (octet-stream): если тип дорожки
    # уже установлен предыдущими чанками — трактуем как его.
    if mime not in MEDIA_TYPES[kind] and lane["type"] and mime in {"", "application/octet-stream"}:
        mime = lane["type"]
    if mime not in MEDIA_TYPES[kind]:
        raise HTTPException(415, "Unsupported track format")
    if not data or len(data) > MAX_CHUNK_BYTES:
        raise HTTPException(413, "Invalid chunk size")
    digest = hashlib.sha256(data).hexdigest()
    if index < len(parts):
        if parts[index]["sha256"] != digest or lane["type"] != mime:
            raise HTTPException(409, "Chunk differs from previously uploaded data")
        return
    if index != len(parts):
        raise HTTPException(409, "Chunk index is out of order")
    if lane["type"] and lane["type"] != mime:
        raise HTTPException(409, "Track format cannot change")
    size = sum(part["size"] for track in upload.manifest.values() for part in track["parts"])
    if size + len(data) > MAX_ANSWER_BYTES:
        raise HTTPException(413, "Answer is too large")
    await storage.put_object(part_key(upload, kind, index), data, content_type=mime)
    upload.manifest = {
        **upload.manifest,
        kind: {"type": mime, "parts": [*parts, {"sha256": digest, "size": len(data)}]},
    }
    await session.commit()


async def complete_upload(
    session: AsyncSession,
    upload: AnswerUpload,
    storage: S3StorageClient,
    video_chunks: int,
    audio_chunks: int,
    duration_sec: int,
) -> Answer:
    """Создаёт Answer только после сохранения двух собранных объектов S3."""
    existing = await session.get(Answer, upload.id)
    if existing is not None:
        return existing
    for kind, count in (("video", video_chunks), ("audio", audio_chunks)):
        if count != len(upload.manifest[kind]["parts"]) or count == 0:
            raise HTTPException(409, "Not all chunks have been uploaded")
    urls = {}
    tracks: tuple[TrackKind, TrackKind] = ("video", "audio")
    for kind in tracks:
        lane = upload.manifest[kind]
        extension = MEDIA_TYPES[kind][lane["type"]]
        target = f"answers/{upload.candidate_id}/{upload.id}/{kind}.{extension}"
        result = await storage.compose_objects(
            [part_key(upload, kind, index) for index in range(len(lane["parts"]))],
            target,
            lane["type"],
        )
        urls[kind] = f"s3://{result.bucket}/{result.key}"
    answer = Answer(
        id=upload.id,
        candidate_id=upload.candidate_id,
        question_id=upload.question_id,
        video_url=urls["video"],
        audio_url=urls["audio"],
        duration_sec=duration_sec,
        processing_status=AnswerProcessingStatus.RECORDED,
    )
    session.add(answer)
    await session.commit()
    await session.refresh(answer)
    return answer
