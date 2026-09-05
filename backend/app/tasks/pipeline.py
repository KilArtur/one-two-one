"""Celery-обёртка оркестрации обработки ответа (транскрибация → анализ → результат)."""

from __future__ import annotations

import asyncio
import uuid
from typing import cast

from celery import Celery
from celery.app.task import Task

from app.db.session import get_sessionmaker
from app.services.pipeline import process_answer


async def _run(answer_id: uuid.UUID) -> dict[str, str]:
    async with get_sessionmaker()() as session:
        answer = await process_answer(session, answer_id)
    status = answer.processing_status.value if answer is not None else "missing"
    return {"answer_id": str(answer_id), "status": status}


def register_pipeline_task(app: Celery) -> Task:
    """Регистрирует задачу обработки ответа на Celery-приложении."""
    existing = app.tasks.get("app.process_answer")
    if existing is not None:
        return cast(Task, existing)

    @app.task(name="app.process_answer")
    def process_answer_task(answer_id: str) -> dict[str, str]:
        return asyncio.run(_run(uuid.UUID(answer_id)))

    return cast(Task, process_answer_task)
