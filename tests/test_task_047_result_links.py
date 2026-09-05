"""Срок и отзыв результата, RBAC, область действия ссылки и аудит просмотров."""

import hashlib
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi import HTTPException
from test_task_026_interview_link_api import ApiFixture, _headers, api
from test_task_040_evidence import seed

from app.models.result_link import ResultLink
from app.services.auth import AppRole
from app.services.result_links import resolve_result_link

__all__ = ["api"]


@pytest.mark.anyio
async def test_issue_thirty_days_hash_storage_and_exact_expiry(api: ApiFixture) -> None:
    client, sessions, candidate_id = api
    before = datetime.now(UTC)
    response = await client.post(f"/candidates/{candidate_id}/result-links")
    assert response.status_code == 201
    data = response.json()
    assert len(data["token"]) >= 43
    expires = datetime.fromisoformat(data["expires_at"]).replace(tzinfo=UTC)
    assert before + timedelta(days=30) <= expires <= datetime.now(UTC) + timedelta(days=30)
    async with sessions() as s:
        link = await s.get(ResultLink, uuid.UUID(data["id"]))
        assert link.token_hash == hashlib.sha256(data["token"].encode()).hexdigest()
        assert not hasattr(link, "token")
        assert (
            await resolve_result_link(s, data["token"], now=expires - timedelta(microseconds=1))
        ).id == link.id
        with pytest.raises(HTTPException) as exc:
            await resolve_result_link(s, data["token"], now=expires)
        assert exc.value.status_code == 403
        link.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        await s.commit()
    assert (
        await client.post("/result-links/resolve", json={"token": data["token"]})
    ).status_code == 403
    listed = (await client.get(f"/candidates/{candidate_id}/result-links")).json()
    assert len(listed) == 1 and "token" not in listed[0] and "token_hash" not in listed[0]


@pytest.mark.anyio
async def test_revocation_blocks_all_scoped_requests_and_is_idempotent(api: ApiFixture) -> None:
    client, _, candidate_id = api
    topic, answer = await seed(api)
    link = (await client.post(f"/candidates/{candidate_id}/result-links")).json()
    base = f"/candidates/{candidate_id}"
    headers = {"X-Result-Link": link["token"]}
    assert (await client.get(f"{base}/result", headers=headers)).status_code == 200
    assert (
        await client.get(f"/candidates/{uuid.uuid4()}/result", headers=headers)
    ).status_code == 403
    assert (
        await client.post("/result-links/resolve", json={"token": link["token"]})
    ).status_code == 200
    first = await client.post(f"/result-links/{link['id']}/revoke")
    assert first.status_code == 200 and first.json()["revoked_at"]
    assert (await client.post(f"/result-links/{link['id']}/revoke")).json() == first.json()
    assert (
        await client.post("/result-links/resolve", json={"token": link["token"]})
    ).status_code == 403
    for path in [
        f"{base}/result",
        f"{base}/transcript",
        f"{base}/topics/{topic}/evidence",
        f"{base}/answers/{answer}/media",
        f"{base}/video-views",
    ]:
        assert (await client.get(path, headers=headers)).status_code == 403
    assert (
        await client.post(
            f"{base}/answers/{answer}/views",
            headers=headers,
            json={"event_id": str(uuid.uuid4()), "position_sec": 1},
        )
    ).status_code == 403
    assert (await client.get(f"{base}/result")).status_code == 200


@pytest.mark.anyio
@pytest.mark.parametrize("role", list(AppRole))
async def test_internal_roles_view_and_audit_but_only_recruiter_manages_links(
    api: ApiFixture, role: AppRole
) -> None:
    client, _, candidate_id = api
    _, answer = await seed(api)
    link = (await client.post(f"/candidates/{candidate_id}/result-links")).json()
    client.headers.update(_headers(role))
    assert (
        await client.post("/result-links/resolve", json={"token": link["token"]})
    ).status_code == 200
    headers = {"X-Result-Link": link["token"]}
    for _ in range(2):
        event = {"event_id": str(uuid.uuid4()), "position_sec": 12}
        for _retry in range(2):
            assert (
                await client.post(
                    f"/candidates/{candidate_id}/answers/{answer}/views",
                    headers=headers,
                    json=event,
                )
            ).status_code == 200
    audit = (await client.get(f"/candidates/{candidate_id}/video-views")).json()
    assert len(audit) == 2
    assert all(v["viewer"] == "test" and v["role"] == role.value and v["created_at"] for v in audit)
    expected = 201 if role == AppRole.RECRUITER else 403
    assert (await client.post(f"/candidates/{candidate_id}/result-links")).status_code == expected
    expected = 200 if role == AppRole.RECRUITER else 403
    assert (await client.post(f"/result-links/{link['id']}/revoke")).status_code == expected


@pytest.mark.anyio
async def test_token_is_not_a_replacement_for_internal_login(api: ApiFixture) -> None:
    client, _, candidate_id = api
    link = (await client.post(f"/candidates/{candidate_id}/result-links")).json()
    assert (
        await client.post("/result-links/resolve", json={"token": "unknown"})
    ).status_code == 403
    assert (await client.post(f"/candidates/{uuid.uuid4()}/result-links")).status_code == 404
    client.headers.clear()
    assert (
        await client.post("/result-links/resolve", json={"token": link["token"]})
    ).status_code == 401
    assert (
        await client.get(
            f"/candidates/{candidate_id}/result", headers={"X-Result-Link": link["token"]}
        )
    ).status_code == 401
    assert (await client.get(f"/candidates/{candidate_id}/video-views")).status_code == 401
