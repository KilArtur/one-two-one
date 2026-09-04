"""Tests for TASK-009 Celery + Redis integration."""

from __future__ import annotations

from app.celery_app import create_celery_app
from app.config import Settings


def test_celery_settings_are_read_from_environment() -> None:
    settings = Settings(
        _env_file=None,
        celery_broker_url="redis://redis:6379/7",
        celery_result_backend="redis://redis:6379/8",
    )

    app = create_celery_app(settings)

    assert app.conf.broker_url == "redis://redis:6379/7"
    assert app.conf.result_backend == "redis://redis:6379/8"
    assert app.conf.task_track_started is True
    assert app.tasks["app.debug_task"].name == "app.debug_task"


def test_debug_task_can_be_enqueued_and_executed_eagerly() -> None:
    settings = Settings(
        _env_file=None,
        celery_broker_url="memory://",
        celery_result_backend="cache+memory://",
    )
    app = create_celery_app(settings)
    app.conf.task_always_eager = True
    app.conf.task_store_eager_result = True

    async_result = app.tasks["app.debug_task"].delay("queue-smoke")
    result = async_result.get(timeout=10)

    assert result["status"] == "ok"
    assert result["payload"] == "queue-smoke"
    assert result["task_id"]
