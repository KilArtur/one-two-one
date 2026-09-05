"""Celery-задачи фоновой обработки."""

from app.tasks.transcription import register_transcription_task

__all__ = ["register_transcription_task"]
