"""Celery-обёртка транскрибации ответа (M5)."""

from __future__ import annotations

import asyncio
import uuid
from typing import cast

from celery import Celery
from celery.app.task import Task

from app.db.session import get_sessionmaker
from app.services.transcription import transcribe_answer


async def _run(answer_id: uuid.UUID) -> dict[str, str]:
    async with get_sessionmaker()() as session:
        answer = await transcribe_answer(session, answer_id)
    status = answer.processing_status.value if answer is not None else "missing"
    return {"answer_id": str(answer_id), "status": status}


def register_transcription_task(app: Celery) -> Task:
    """Регистрирует задачу транскрибации на Celery-приложении."""
    existing = app.tasks.get("app.transcribe_answer")
    if existing is not None:
        return cast(Task, existing)

    @app.task(name="app.transcribe_answer")
    def transcribe_answer_task(answer_id: str) -> dict[str, str]:
        return asyncio.run(_run(uuid.UUID(answer_id)))

    return cast(Task, transcribe_answer_task)
