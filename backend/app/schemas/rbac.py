"""Схемы RBAC check-endpoints."""

from __future__ import annotations

from pydantic import BaseModel

from app.models.topic import SkillType


class TopicStatusChangeCheck(BaseModel):
    """Проверка права смены статуса топика по типу навыка."""

    skill_type: SkillType


class RbacCheckResult(BaseModel):
    """Успешный результат RBAC-проверки."""

    allowed: bool = True
    reason: str
