"""JWT-аутентификация внутренних ролей (TASK-023)."""

from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.auth import get_me
from app.config import Settings
from app.db import get_db
from app.integrations.llm import get_llm_client
from app.main import create_app
from app.models.staff_user import StaffUser
from app.services.auth import decode_access_token, get_current_user


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="testing",
        jwt_secret_key="task-023-secret",
        internal_auth_password="letmein",
    )


class StaffSessionStub:
    """In-memory сессия для register/login без Postgres."""

    def __init__(self) -> None:
        self.users: dict[str, StaffUser] = {}

    async def scalar(self, statement: object) -> StaffUser | None:
        del statement
        # login/register всегда ищут по username — отдаём единственный способ через last lookup
        return self._pending_lookup

    def set_lookup(self, username: str) -> None:
        self._pending_lookup = self.users.get(username)

    def add(self, user: StaffUser) -> None:
        self.users[user.username] = user
        self._pending_lookup = None

    async def commit(self) -> None:
        return None

    _pending_lookup: StaffUser | None = None


@pytest.fixture
async def staff_session() -> StaffSessionStub:
    return StaffSessionStub()


@pytest.fixture
async def client(staff_session: StaffSessionStub) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(_settings())

    class _FakeLLM:
        pass

    async def override_db() -> AsyncIterator[StaffSessionStub]:
        yield staff_session

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_llm_client] = lambda: _FakeLLM()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
        yield test_client


@pytest.mark.anyio
async def test_login_returns_jwt_with_role_claim(
    client: httpx.AsyncClient, staff_session: StaffSessionStub
) -> None:
    staff_session.set_lookup("alice")
    response = await client.post(
        "/auth/token",
        json={
            "username": "alice",
            "password": "letmein",
            "role": "technical_specialist",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    user = decode_access_token(body["access_token"], settings=_settings())
    assert user.username == "alice"
    assert user.role.value == "technical_specialist"


def test_protected_endpoint_rejects_missing_token() -> None:
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials=None, settings=_settings())

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid authentication credentials"


@pytest.mark.anyio
async def test_protected_endpoint_accepts_valid_token(
    client: httpx.AsyncClient, staff_session: StaffSessionStub
) -> None:
    staff_session.set_lookup("recruiter-1")
    login = await client.post(
        "/auth/token",
        json={"username": "recruiter-1", "password": "letmein", "role": "recruiter"},
    )
    token = login.json()["access_token"]
    current_user = get_current_user(
        credentials=HTTPAuthorizationCredentials(scheme="Bearer", credentials=token),
        settings=_settings(),
    )
    response = await get_me(current_user)

    assert response.model_dump() == {"username": "recruiter-1", "role": "recruiter"}


@pytest.mark.anyio
async def test_register_then_login(
    client: httpx.AsyncClient, staff_session: StaffSessionStub
) -> None:
    staff_session.set_lookup("bob")
    created = await client.post(
        "/auth/register",
        json={"username": "bob", "password": "secret-pass", "role": "recruiter"},
    )
    assert created.status_code == 201
    assert "access_token" in created.json()
    assert "bob" in staff_session.users

    staff_session.set_lookup("bob")
    duplicate = await client.post(
        "/auth/register",
        json={"username": "bob", "password": "other", "role": "recruiter"},
    )
    assert duplicate.status_code == 409

    staff_session.set_lookup("bob")
    login = await client.post(
        "/auth/token",
        json={"username": "bob", "password": "secret-pass", "role": "recruiter"},
    )
    assert login.status_code == 200

    staff_session.set_lookup("bob")
    wrong = await client.post(
        "/auth/token",
        json={"username": "bob", "password": "letmein", "role": "recruiter"},
    )
    assert wrong.status_code == 401
