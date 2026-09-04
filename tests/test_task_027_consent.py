"""Проверки согласия и запрета обхода через API (TASK-027)."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from test_task_026_interview_link_api import ApiFixture, api

from app.models.candidate import Candidate
from app.models.interview_link import InterviewLink

__all__ = ["api"]


async def _candidate(api: ApiFixture) -> tuple[str, uuid.UUID]:
    client, sessions, candidate_id = api
    async with sessions() as session:
        candidate = await session.get(Candidate, candidate_id)
        assert candidate is not None
        candidate.consent_given_at = None
        await session.commit()
    link = (await client.post(f"/candidates/{candidate_id}/interview-link")).json()
    exchange = await client.post("/candidate-auth/exchange", json={"token": link["token"]})
    client.headers["Authorization"] = f"Bearer {exchange.json()['access_token']}"
    return link["token"], uuid.UUID(link["id"])


@pytest.mark.anyio
async def test_consent_required_saved_and_equipment_allowed(api: ApiFixture) -> None:
    client, sessions, candidate_id = api
    await _candidate(api)
    assert (await client.get("/candidate-auth/consent")).json() == {"consent_given_at": None}
    assert (await client.get("/candidate-auth/equipment-check")).status_code == 403
    assert (await client.post("/candidate-auth/submit")).status_code == 403
    before = datetime.now(UTC)
    response = await client.post("/candidate-auth/consent", json={"accepted": True})
    assert response.status_code == 200
    timestamp = datetime.fromisoformat(response.json()["consent_given_at"]).replace(tzinfo=UTC)
    assert before <= timestamp <= datetime.now(UTC)
    async with sessions() as session:
        candidate = await session.get(Candidate, candidate_id)
        assert candidate.consent_given_at.replace(tzinfo=UTC) == timestamp
    repeated = await client.post("/candidate-auth/consent", json={"accepted": True})
    assert (
        datetime.fromisoformat(repeated.json()["consent_given_at"]).replace(tzinfo=UTC) == timestamp
    )
    assert (await client.get("/candidate-auth/equipment-check")).status_code == 200


@pytest.mark.anyio
@pytest.mark.parametrize(
    "body",
    [
        {},
        {"accepted": False},
        {"accepted": "true"},
        {"accepted": 1},
        {"accepted": True, "consent_given_at": "2020-01-01"},
    ],
)
async def test_only_explicit_consent_is_accepted(api: ApiFixture, body: dict) -> None:
    client, sessions, candidate_id = api
    await _candidate(api)
    assert (await client.post("/candidate-auth/consent", json=body)).status_code == 422
    async with sessions() as session:
        assert (await session.get(Candidate, candidate_id)).consent_given_at is None


@pytest.mark.anyio
@pytest.mark.parametrize("state", ["revoked", "expired", "used", "foreign"])
async def test_invalid_link_cannot_give_consent(api: ApiFixture, state: str) -> None:
    client, sessions, candidate_id = api
    _, link_id = await _candidate(api)
    async with sessions() as session:
        link = await session.get(InterviewLink, link_id)
        if state == "revoked":
            link.revoked = True
        elif state == "expired":
            link.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        elif state == "used":
            link.used_at = datetime.now(UTC)
        else:
            candidate = await session.get(Candidate, candidate_id)
            other = Candidate(vacancy_id=candidate.vacancy_id)
            session.add(other)
            await session.flush()
            link.candidate_id = other.id
        await session.commit()
    assert (
        await client.post("/candidate-auth/consent", json={"accepted": True})
    ).status_code == 403
    assert (await client.get("/candidate-auth/consent")).status_code == 403
    assert (await client.get("/candidate-auth/equipment-check")).status_code == 403
    async with sessions() as session:
        assert (await session.get(Candidate, candidate_id)).consent_given_at is None


@pytest.mark.anyio
async def test_consent_requires_candidate_auth(api: ApiFixture) -> None:
    client, _, _ = api
    assert (
        await client.post("/candidate-auth/consent", json={"accepted": True})
    ).status_code == 401
    client.headers.clear()
    assert (await client.get("/candidate-auth/consent")).status_code == 401
