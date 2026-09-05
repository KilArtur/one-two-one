"""Ретенция 6 месяцев (Р18): удаление ПДн, сохранение обезличенных агрегатов.

Удаляет видео/аудио/транскрипты/резюме кандидатов старше срока хранения из S3 и БД,
сохраняя `InterviewResult` (обезличенный агрегат для метрик). Досрочное удаление — по
запросу. Каждое удаление фиксируется в append-only `DataDeletionLog`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.storage import S3StorageClient, S3StorageError, get_s3_storage_client
from app.models.answer import Answer
from app.models.answer_upload import AnswerUpload
from app.models.candidate import Candidate
from app.models.data_deletion import DataDeletionLog

RETENTION_DAYS = 180


def _object_key(url: str) -> str:
    return url.split("/", 3)[3]


async def _delete_quietly(storage: S3StorageClient, key: str) -> int:
    try:
        await storage.delete_object(key)
        return 1
    except S3StorageError:
        return 0


async def purge_candidate(
    session: AsyncSession,
    storage: S3StorageClient,
    candidate_id: uuid.UUID,
    *,
    reason: str,
    force_log: bool = False,
) -> DataDeletionLog | None:
    """Удаляет ПДн кандидата из S3/БД, сохраняя InterviewResult; пишет лог удаления."""
    candidate = await session.get(Candidate, candidate_id)
    if candidate is None:
        return None

    removed_objects = 0
    answer_pii_cleared = 0
    answers = list(
        await session.scalars(select(Answer).where(Answer.candidate_id == candidate_id))
    )
    for answer in answers:
        if any(
            (answer.video_url, answer.audio_url, answer.transcript, answer.transcript_segments)
        ):
            answer_pii_cleared += 1
        for url in (answer.video_url, answer.audio_url):
            if url:
                removed_objects += await _delete_quietly(storage, _object_key(url))
        answer.video_url = None
        answer.audio_url = None
        answer.transcript = None
        answer.transcript_segments = None

    uploads = list(
        await session.scalars(
            select(AnswerUpload).where(AnswerUpload.candidate_id == candidate_id)
        )
    )
    for upload in uploads:
        for kind in ("video", "audio"):
            parts = upload.manifest.get(kind, {}).get("parts", [])
            for index in range(len(parts)):
                key = f"answers/{upload.candidate_id}/{upload.id}/parts/{kind}/{index:04d}"
                removed_objects += await _delete_quietly(storage, key)
        await session.delete(upload)

    resume_cleared = bool(candidate.resume_text or candidate.resume_file_url)
    candidate.resume_text = None
    candidate.resume_file_url = None

    purged_anything = bool(removed_objects or answer_pii_cleared or uploads or resume_cleared)
    log: DataDeletionLog | None = None
    if purged_anything or force_log:
        log = DataDeletionLog(
            candidate_id=candidate_id,
            reason=reason,
            details={
                "removed_objects": removed_objects,
                "answers_cleared": answer_pii_cleared,
                "uploads": len(uploads),
                "resume_cleared": resume_cleared,
            },
        )
        session.add(log)

    await session.commit()
    if log is not None:
        await session.refresh(log)
    return log


async def purge_expired(
    session: AsyncSession,
    storage: S3StorageClient | None = None,
    *,
    now: datetime | None = None,
    retention_days: int = RETENTION_DAYS,
) -> list[uuid.UUID]:
    """Удаляет ПДн всех кандидатов старше срока хранения (для Celery-beat)."""
    storage = storage or get_s3_storage_client()
    now = now or datetime.now(UTC)
    cutoff = now - timedelta(days=retention_days)

    candidates = list(
        await session.scalars(select(Candidate).where(Candidate.created_at < cutoff))
    )
    purged: list[uuid.UUID] = []
    for candidate in candidates:
        log = await purge_candidate(
            session, storage, candidate.id, reason="retention", force_log=False
        )
        if log is not None:
            purged.append(candidate.id)
    return purged
