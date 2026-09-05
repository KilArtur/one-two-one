"""Celery-задачи фоновой обработки."""

from app.tasks.pipeline import register_pipeline_task
from app.tasks.transcription import register_transcription_task

__all__ = ["register_pipeline_task", "register_transcription_task"]
