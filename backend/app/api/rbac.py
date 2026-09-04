"""RBAC check-endpoints для матрицы прав внутренних ролей."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends

from app.schemas.rbac import RbacCheckResult, TopicStatusChangeCheck
from app.services.auth import (
    CurrentUser,
    ensure_interview_link_issue_allowed,
    ensure_topic_status_change_allowed,
    get_current_user,
)

router = APIRouter(prefix="/rbac", tags=["rbac"])

CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


@router.patch("/topic-status-check", response_model=RbacCheckResult)
async def check_topic_status_change(
    data: TopicStatusChangeCheck,
    current_user: CurrentUserDep,
) -> RbacCheckResult:
    """Проверяет, может ли роль менять статус hard/soft топика."""
    ensure_topic_status_change_allowed(current_user, data.skill_type)
    return RbacCheckResult(
        reason=f"{current_user.role.value} may change {data.skill_type.value} topic"
    )


@router.post("/interview-links/issue-check", response_model=RbacCheckResult)
async def check_interview_link_issue(current_user: CurrentUserDep) -> RbacCheckResult:
    """Проверяет, может ли роль выпускать ссылку интервью."""
    ensure_interview_link_issue_allowed(current_user)
    return RbacCheckResult(reason="recruiter may issue interview links")
