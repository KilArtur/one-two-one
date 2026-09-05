"""Celery application and debug task registration."""

from __future__ import annotations

from functools import lru_cache
from typing import cast

from celery import Celery
from celery.app.task import Task
from celery.utils.log import get_task_logger

from app.config import Settings, get_settings

logger = get_task_logger(__name__)


def create_celery_app(settings: Settings | None = None) -> Celery:
    """Builds a Celery application configured from project settings."""
    settings = settings or get_settings()
    app = Celery("one_two_one")
    app.conf.update(
        broker_url=settings.celery_broker_url,
        result_backend=settings.celery_result_backend,
        task_default_queue="default",
        task_track_started=True,
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
    )
    register_debug_task(app)
    from celery.schedules import crontab

    from app.tasks.local_pipeline import register_pending_task
    from app.tasks.pipeline import register_pipeline_task
    from app.tasks.retention import register_retention_task
    from app.tasks.transcription import register_transcription_task

    register_transcription_task(app)
    register_pipeline_task(app)
    register_pending_task(app)
    register_retention_task(app)
    app.conf.beat_schedule = {
        "process-pending-interviews": {
            "task": "app.process_pending",
            "schedule": 5.0,
        },
        "purge-expired-data": {
            "task": "app.purge_expired_data",
            "schedule": crontab(hour=3, minute=0),
        },
    }
    return app


def register_debug_task(app: Celery) -> Task:
    """Registers the debug task on a Celery app and returns it."""
    existing = app.tasks.get("app.debug_task")
    if existing is not None:
        return cast(Task, existing)

    @app.task(bind=True, name="app.debug_task")
    def debug_task(self, payload: str = "ping") -> dict[str, str]:
        logger.info("debug_task executed id=%s payload=%s", self.request.id, payload)
        return {
            "task_id": self.request.id,
            "payload": payload,
            "status": "ok",
        }

    return cast(Task, debug_task)


@lru_cache
def get_celery_app() -> Celery:
    """Returns a cached Celery application."""
    return create_celery_app()


celery_app = get_celery_app()


debug_task = register_debug_task(celery_app)
