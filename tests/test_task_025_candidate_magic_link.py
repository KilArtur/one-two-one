"""Магические ссылки кандидата и короткая JWT-сессия (TASK-025)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from app.api.candidate_auth import exchange_candidate_link, get_candidate_me
from app.config import Settings
from app.models.candidate import Candidate
from app.models.interview_link import InterviewLink
from app.models.vacancy import Vacancy, VacancyGrade
from app.schemas.candidate_auth import CandidateSessionExchangeRequest
from app.services.auth import (
    create_candidate_access_token,
    exchange_interview_link_token,
    get_candidate_session,
)


class FakeAsyncSession:
    """Минимальный async session stub для тестов обмена magic link."""

    def __init__(self, link: InterviewLink | None) -> None:
        self._link = link
        self.last_statement: Any = None

    async def scalar(self, statement: Any) -> InterviewLink | None:
        self.last_statement = statement
        return self._link


def _seed_link(
    *,
    token: str = "candidate-magic-token",
    expires_at: datetime | None = None,
    revoked: bool = False,
    used_at: datetime | None = None,
) -> tuple[FakeAsyncSession, uuid.UUID, uuid.UUID]:
    vacancy = Vacancy(id=uuid.uuid4(), title="Backend", grade=VacancyGrade.MIDDLE)
    vacancy.lineage_id = vacancy.id
    candidate_id = uuid.uuid4()
    link_id = uuid.uuid4()
    candidate = Candidate(id=candidate_id, vacancy_id=vacancy.id)
    link = InterviewLink(
        id=link_id,
        candidate_id=candidate.id,
        token=token,
        expires_at=expires_at or (datetime.now(UTC) + timedelta(days=7)),
        revoked=revoked,
        used_at=used_at,
    )
    return FakeAsyncSession(link), candidate_id, link_id


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="testing",
        jwt_secret_key="task-025-secret",
        candidate_jwt_access_token_ttl_seconds=900,
    )


@pytest.mark.anyio
async def test_valid_link_exchanges_to_candidate_session() -> None:
    session, candidate_id, link_id = _seed_link()

    response = await exchange_candidate_link(
        CandidateSessionExchangeRequest(token="candidate-magic-token"),
        session,
        _settings(),
    )

    assert response.candidate_id == candidate_id
    session_data = get_candidate_session(
        credentials=type("Creds", (), {"scheme": "Bearer", "credentials": response.access_token})(),
        settings=_settings(),
    )
    assert session_data.candidate_id == candidate_id
    assert session_data.interview_link_id == link_id


@pytest.mark.anyio
async def test_revoked_link_rejected() -> None:
    session, _, _ = _seed_link(token="revoked-token", revoked=True)

    with pytest.raises(Exception) as exc_info:
        await exchange_interview_link_token(session, "revoked-token", settings=_settings())

    assert getattr(exc_info.value, "status_code", None) == 403


@pytest.mark.anyio
async def test_expired_link_rejected() -> None:
    session, _, _ = _seed_link(
        token="expired-token",
        expires_at=datetime.now(UTC) - timedelta(minutes=1),
    )

    with pytest.raises(Exception) as exc_info:
        await exchange_interview_link_token(session, "expired-token", settings=_settings())

    assert getattr(exc_info.value, "status_code", None) == 403


@pytest.mark.anyio
async def test_used_link_rejected_after_submit() -> None:
    session, _, _ = _seed_link(
        token="used-token",
        used_at=datetime.now(UTC),
    )

    with pytest.raises(Exception) as exc_info:
        await exchange_interview_link_token(session, "used-token", settings=_settings())

    assert getattr(exc_info.value, "status_code", None) == 403


@pytest.mark.anyio
async def test_candidate_me_returns_candidate_session() -> None:
    _, candidate_id, link_id = _seed_link(token="me-token")
    token = create_candidate_access_token(
        candidate_id=candidate_id,
        interview_link_id=link_id,
        settings=_settings(),
    )
    candidate_session = get_candidate_session(
        credentials=type("Creds", (), {"scheme": "Bearer", "credentials": token})(),
        settings=_settings(),
    )

    response = await get_candidate_me(candidate_session)

    assert response.model_dump() == {
        "candidate_id": candidate_id,
        "interview_link_id": link_id,
    }
