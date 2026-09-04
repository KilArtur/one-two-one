"""HTTP-проверки выпуска, отзыва и гашения InterviewLink (TASK-026)."""

import uuid
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.db import Base, get_db
from app.main import create_app
from app.models.candidate import Candidate, CandidateStatus
from app.models.interview_link import InterviewLink
from app.models.vacancy import Vacancy, VacancyGrade
from app.services.auth import AppRole, create_access_token, create_candidate_access_token
from app.services.interview_link import submit_candidate_interview

type ApiFixture = tuple[httpx.AsyncClient, async_sessionmaker[AsyncSession], uuid.UUID]

SETTINGS = Settings(_env_file=None, app_env="testing", jwt_secret_key="task-026-test-secret")


def _headers(role: AppRole = AppRole.RECRUITER) -> dict[str, str]:
    token = create_access_token(username="test", role=role, settings=SETTINGS)
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
async def api() -> AsyncIterator[ApiFixture]:
    engine = create_async_engine("sqlite+aiosqlite://", poolclass=StaticPool)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    async with sessions() as session:
        vacancy = Vacancy(title="Backend", grade=VacancyGrade.MIDDLE)
        session.add(vacancy)
        await session.flush()
        candidate = Candidate(vacancy_id=vacancy.id, consent_given_at=datetime.now(UTC))
        session.add(candidate)
        await session.commit()
        candidate_id = candidate.id

    async def override_get_db() -> AsyncIterator[AsyncSession]:
        async with sessions() as session:
            yield session

    app = create_app(SETTINGS)
    app.dependency_overrides[get_db] = override_get_db
    try:
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app), base_url="http://test", headers=_headers()
        ) as client:
            yield client, sessions, candidate_id
    finally:
        await engine.dispose()


@pytest.mark.anyio
async def test_issue_revoke_and_get(api: ApiFixture) -> None:
    client, sessions, candidate_id = api
    before = datetime.now(UTC)
    response = await client.post(f"/candidates/{candidate_id}/interview-link")
    assert response.status_code == 201
    link = response.json()
    assert len(link["token"]) >= 32
    assert link["candidate_id"] == str(candidate_id)
    assert link["used_at"] is None
    assert link["revoked"] is False
    expires_at = datetime.fromisoformat(link["expires_at"]).replace(tzinfo=UTC)
    assert before + timedelta(days=7) <= expires_at <= datetime.now(UTC) + timedelta(days=7)
    another = (await client.post(f"/candidates/{candidate_id}/interview-link")).json()
    assert another["token"] != link["token"]
    exchanged = await client.post("/candidate-auth/exchange", json={"token": link["token"]})
    assert exchanged.status_code == 200
    assert (await client.post(f"/interview-links/{link['id']}/revoke")).status_code == 200
    fetched = await client.get(f"/interview-links/{link['id']}")
    assert fetched.status_code == 200
    assert fetched.json()["revoked"] is True
    assert (
        await client.post("/candidate-auth/exchange", json={"token": link["token"]})
    ).status_code == 403
    async with sessions() as session:
        stored = await session.get(InterviewLink, uuid.UUID(link["id"]))
        assert stored.revoked is True


@pytest.mark.anyio
async def test_submit_consumes_link_and_rejects_replay(api: ApiFixture) -> None:
    client, sessions, candidate_id = api
    link = (await client.post(f"/candidates/{candidate_id}/interview-link")).json()
    exchanged = await client.post("/candidate-auth/exchange", json={"token": link["token"]})
    headers = {"Authorization": f"Bearer {exchanged.json()['access_token']}"}
    response = await client.post("/candidate-auth/submit", headers=headers)
    assert response.status_code == 200
    assert response.json()["candidate_status"] == "submitted"
    used_at = response.json()["used_at"]
    assert used_at is not None
    fetched = await client.get(f"/interview-links/{link['id']}")
    assert fetched.json()["used_at"] == used_at
    assert (await client.post("/candidate-auth/submit", headers=headers)).status_code == 403
    assert (
        await client.post("/candidate-auth/exchange", json={"token": link["token"]})
    ).status_code == 403
    async with sessions() as session:
        assert (await session.get(Candidate, candidate_id)).status == CandidateStatus.SUBMITTED
        assert (await session.get(InterviewLink, uuid.UUID(link["id"]))).used_at is not None


@pytest.mark.anyio
@pytest.mark.parametrize("invalid", ["revoked", "expired", "used", "foreign", "missing"])
async def test_invalid_link_cannot_submit_with_existing_jwt(api: ApiFixture, invalid: str) -> None:
    client, sessions, candidate_id = api
    link = (await client.post(f"/candidates/{candidate_id}/interview-link")).json()
    link_id = uuid.UUID(link["id"])
    async with sessions() as session:
        stored = await session.get(InterviewLink, link_id)
        if invalid == "revoked":
            stored.revoked = True
        elif invalid == "expired":
            stored.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        elif invalid == "used":
            stored.used_at = datetime.now(UTC) - timedelta(minutes=1)
        elif invalid == "foreign":
            owner = await session.get(Candidate, candidate_id)
            other = Candidate(vacancy_id=owner.vacancy_id)
            session.add(other)
            await session.flush()
            stored.candidate_id = other.id
        elif invalid == "missing":
            link_id = uuid.uuid4()
        await session.commit()
        original_used_at = stored.used_at.replace(tzinfo=None) if stored.used_at else None
    token = create_candidate_access_token(
        candidate_id=candidate_id, interview_link_id=link_id, settings=SETTINGS
    )
    response = await client.post(
        "/candidate-auth/submit", headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 403
    async with sessions() as session:
        assert (await session.get(Candidate, candidate_id)).status == CandidateStatus.INVITED
        stored = await session.get(InterviewLink, uuid.UUID(link["id"]))
        assert stored.used_at == original_used_at


@pytest.mark.anyio
async def test_expiration_boundary_is_rejected(api: ApiFixture) -> None:
    client, sessions, candidate_id = api
    link = (await client.post(f"/candidates/{candidate_id}/interview-link")).json()
    async with sessions() as session:
        result = await submit_candidate_interview(
            session,
            candidate_id=candidate_id,
            interview_link_id=uuid.UUID(link["id"]),
            now=datetime.fromisoformat(link["expires_at"]).replace(tzinfo=UTC),
        )
        assert result is None


@pytest.mark.anyio
@pytest.mark.parametrize("role", [AppRole.TECH_SPECIALIST, AppRole.HIRING_MANAGER, None])
async def test_management_requires_recruiter(api: ApiFixture, role: AppRole | None) -> None:
    client, _, candidate_id = api
    link = (await client.post(f"/candidates/{candidate_id}/interview-link")).json()
    client.headers.clear()
    headers = _headers(role) if role else {}
    expected = 403 if role else 401
    assert (
        await client.post(f"/candidates/{candidate_id}/interview-link", headers=headers)
    ).status_code == expected
    assert (
        await client.get(f"/interview-links/{link['id']}", headers=headers)
    ).status_code == expected
    assert (
        await client.post(f"/interview-links/{link['id']}/revoke", headers=headers)
    ).status_code == expected


@pytest.mark.anyio
async def test_missing_resources_and_submit_auth(api: ApiFixture) -> None:
    client, _, _ = api
    missing = uuid.uuid4()
    assert (await client.post(f"/candidates/{missing}/interview-link")).status_code == 404
    assert (await client.get(f"/interview-links/{missing}")).status_code == 404
    assert (await client.post(f"/interview-links/{missing}/revoke")).status_code == 404
    assert (await client.post("/candidate-auth/submit")).status_code == 401
    client.headers.clear()
    assert (await client.post("/candidate-auth/submit")).status_code == 401
