"""Celery-обёртка периодического удаления по ретенции (Р18)."""

from __future__ import annotations

from typing import cast

from celery import Celery
from celery.app.task import Task

from app.db.session import get_sessionmaker
from app.services.retention import purge_expired


async def _run() -> dict[str, int]:
    async with get_sessionmaker()() as session:
        purged = await purge_expired(session)
    return {"purged": len(purged)}


def register_retention_task(app: Celery) -> Task:
    """Регистрирует периодическую задачу ретенции на Celery-приложении."""
    existing = app.tasks.get("app.purge_expired_data")
    if existing is not None:
        return cast(Task, existing)

    @app.task(name="app.purge_expired_data")
    def purge_expired_data_task() -> dict[str, int]:
        import asyncio

        return asyncio.run(_run())

    return cast(Task, purge_expired_data_task)
