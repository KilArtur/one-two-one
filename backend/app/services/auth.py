"""JWT-аутентификация внутренних ролей без зависимости от внешнего auth-провайдера."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.config import Settings, get_settings

_ALGORITHM = "HS256"
_TOKEN_TYPE = "JWT"
_bearer_scheme = HTTPBearer(auto_error=False)


class AppRole(StrEnum):
    """Внутренние роли системы."""

    RECRUITER = "recruiter"
    TECH_SPECIALIST = "technical_specialist"
    HIRING_MANAGER = "hiring_manager"


@dataclass(slots=True, frozen=True)
class CurrentUser:
    """Авторизованный внутренний пользователь."""

    username: str
    role: AppRole


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _sign(signing_input: str, secret: str) -> str:
    digest = hmac.new(
        secret.encode("utf-8"),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return _b64url_encode(digest)


def _invalid_credentials() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def create_access_token(
    *,
    username: str,
    role: AppRole,
    settings: Settings | None = None,
    now: int | None = None,
) -> str:
    """Выпускает HMAC-SHA256 JWT с ролью в claims."""
    settings = settings or get_settings()
    issued_at = now or int(time.time())
    payload = {
        "sub": username,
        "role": role.value,
        "iat": issued_at,
        "exp": issued_at + settings.jwt_access_token_ttl_seconds,
    }
    header = {"alg": _ALGORITHM, "typ": _TOKEN_TYPE}
    segments = [
        _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8")),
        _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8")),
    ]
    signing_input = ".".join(segments)
    signature = _sign(signing_input, settings.jwt_secret_key)
    return f"{signing_input}.{signature}"


def decode_access_token(token: str, settings: Settings | None = None) -> CurrentUser:
    """Проверяет подпись/exp и восстанавливает текущего пользователя."""
    settings = settings or get_settings()
    parts = token.split(".")
    if len(parts) != 3:
        raise _invalid_credentials()

    signing_input = ".".join(parts[:2])
    expected_signature = _sign(signing_input, settings.jwt_secret_key)
    if not hmac.compare_digest(parts[2], expected_signature):
        raise _invalid_credentials()

    try:
        payload: dict[str, Any] = json.loads(_b64url_decode(parts[1]))
        username = str(payload["sub"])
        role = AppRole(str(payload["role"]))
        expires_at = int(payload["exp"])
    except (KeyError, ValueError, json.JSONDecodeError):
        raise _invalid_credentials() from None

    if expires_at < int(time.time()):
        raise _invalid_credentials()

    return CurrentUser(username=username, role=role)


def authenticate_internal_user(
    *,
    username: str,
    password: str,
    role: str,
    settings: Settings | None = None,
) -> CurrentUser | None:
    """Проверяет простой внутренний пароль и допустимую роль."""
    settings = settings or get_settings()
    try:
        parsed_role = AppRole(role)
    except ValueError:
        return None

    if password != settings.internal_auth_password:
        return None

    return CurrentUser(username=username, role=parsed_role)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> CurrentUser:
    """Dependency FastAPI: валидирует Bearer JWT."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _invalid_credentials()
    return decode_access_token(credentials.credentials, settings=settings)
