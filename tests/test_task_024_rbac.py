"""RBAC по матрице прав внутренних ролей (TASK-024)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.rbac import check_interview_link_issue, check_topic_status_change
from app.models.topic import SkillType
from app.schemas.rbac import TopicStatusChangeCheck
from app.services.auth import AppRole, CurrentUser


def _user(role: AppRole) -> CurrentUser:
    return CurrentUser(username=f"{role.value}-user", role=role)


@pytest.mark.anyio
async def test_recruiter_cannot_change_topic_status() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await check_topic_status_change(
            TopicStatusChangeCheck(skill_type=SkillType.HARD),
            _user(AppRole.RECRUITER),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Recruiter cannot change topic statuses"


@pytest.mark.anyio
async def test_technical_specialist_can_change_hard_but_not_soft() -> None:
    allowed = await check_topic_status_change(
        TopicStatusChangeCheck(skill_type=SkillType.HARD),
        _user(AppRole.TECH_SPECIALIST),
    )
    assert allowed.allowed is True

    with pytest.raises(HTTPException) as exc_info:
        await check_topic_status_change(
            TopicStatusChangeCheck(skill_type=SkillType.SOFT),
            _user(AppRole.TECH_SPECIALIST),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Only hiring manager can change soft-topic status"


@pytest.mark.anyio
async def test_hiring_manager_can_change_soft_but_not_hard() -> None:
    allowed = await check_topic_status_change(
        TopicStatusChangeCheck(skill_type=SkillType.SOFT),
        _user(AppRole.HIRING_MANAGER),
    )
    assert allowed.allowed is True

    with pytest.raises(HTTPException) as exc_info:
        await check_topic_status_change(
            TopicStatusChangeCheck(skill_type=SkillType.HARD),
            _user(AppRole.HIRING_MANAGER),
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Only technical specialist can change hard-topic status"


@pytest.mark.anyio
async def test_only_recruiter_can_issue_interview_link() -> None:
    allowed = await check_interview_link_issue(_user(AppRole.RECRUITER))
    assert allowed.allowed is True

    with pytest.raises(HTTPException) as exc_info:
        await check_interview_link_issue(_user(AppRole.TECH_SPECIALIST))

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "Only recruiter can issue interview links"
