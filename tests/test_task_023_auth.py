"""JWT-аутентификация внутренних ролей (TASK-023)."""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.api.auth import get_me, login_for_access_token
from app.config import Settings
from app.schemas.auth import AuthTokenRequest
from app.services.auth import decode_access_token, get_current_user


def _settings() -> Settings:
    return Settings(
        _env_file=None,
        app_env="testing",
        jwt_secret_key="task-023-secret",
        internal_auth_password="letmein",
    )


@pytest.mark.anyio
async def test_login_returns_jwt_with_role_claim() -> None:
    result = await login_for_access_token(
        AuthTokenRequest(
            username="alice",
            password="letmein",
            role="technical_specialist",
        ),
        _settings(),
    )

    assert result.token_type == "bearer"
    user = decode_access_token(result.access_token, settings=_settings())
    assert user.username == "alice"
    assert user.role.value == "technical_specialist"


def test_protected_endpoint_rejects_missing_token() -> None:
    with pytest.raises(HTTPException) as exc_info:
        get_current_user(credentials=None, settings=_settings())

    assert exc_info.value.status_code == 401
    assert exc_info.value.detail == "Invalid authentication credentials"


@pytest.mark.anyio
async def test_protected_endpoint_accepts_valid_token() -> None:
    login_result = await login_for_access_token(
        AuthTokenRequest(
            username="recruiter-1",
            password="letmein",
            role="recruiter",
        ),
        _settings(),
    )
    current_user = get_current_user(
        credentials=HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials=login_result.access_token,
        ),
        settings=_settings(),
    )
    response = await get_me(current_user)

    assert response.model_dump() == {"username": "recruiter-1", "role": "recruiter"}
