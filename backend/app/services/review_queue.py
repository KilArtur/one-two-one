"""Очередь ревью спорных топиков по ролям (M7, принцип 5).

Техспециалист разбирает hard-топики, нанимающий менеджер — soft; рекрутер статусы не
меняет и очереди не имеет. В очередь попадают только топики со статусом `needs_check`,
которые ещё не сохранял эксперт (`reviewed_by IS NULL`). После сохранения
статуса (даже без смены значения) топик уходит из очереди. Сортировка:
самое неопределённое сверху (low → medium → high).
"""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.topic import SkillType, Topic
from app.models.topic_assessment import AssessmentConfidence, AssessmentStatus, TopicAssessment
from app.services.auth import AppRole, CurrentUser

_ROLE_SKILL: dict[AppRole, SkillType] = {
    AppRole.TECH_SPECIALIST: SkillType.HARD,
    AppRole.HIRING_MANAGER: SkillType.SOFT,
}
_CONFIDENCE_RANK: dict[AssessmentConfidence, int] = {
    AssessmentConfidence.LOW: 0,
    AssessmentConfidence.MEDIUM: 1,
    AssessmentConfidence.HIGH: 2,
}


def reviewer_skill_type(user: CurrentUser) -> SkillType:
    """Возвращает тип топиков, доступных роли для ревью (иначе 403)."""
    skill = _ROLE_SKILL.get(user.role)
    if skill is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Recruiter has no review queue",
        )
    return skill


async def review_queue(session: AsyncSession, user: CurrentUser) -> list[dict]:
    """Возвращает спорные топики роли, отсортированные по возрастанию уверенности."""
    skill = reviewer_skill_type(user)
    rows = list(
        await session.scalars(
            select(TopicAssessment)
            .join(Topic, Topic.id == TopicAssessment.topic_id)
            .where(
                TopicAssessment.current_status == AssessmentStatus.NEEDS_CHECK,
                TopicAssessment.reviewed_by.is_(None),
                Topic.skill_type == skill,
            )
        )
    )
    items = [
        {
            "assessment_id": row.id,
            "candidate_id": row.candidate_id,
            "topic_id": row.topic_id,
            "topic_title": row.topic.title,
            "skill_type": row.topic.skill_type.value,
            "confidence": row.confidence,
            "current_status": row.current_status,
            "reasoning_summary": row.reasoning_summary,
        }
        for row in rows
    ]
    items.sort(key=lambda item: (_CONFIDENCE_RANK[item["confidence"]], str(item["assessment_id"])))
    return items
