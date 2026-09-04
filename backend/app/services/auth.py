"""JWT-аутентификация внутренних ролей без зависимости от внешнего auth-провайдера."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import uuid
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import Settings, get_settings
from app.models.interview_link import InterviewLink
from app.models.topic import SkillType

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


@dataclass(slots=True, frozen=True)
class CandidateSession:
    """Короткая JWT-сессия кандидата, выданная по magic link."""

    candidate_id: uuid.UUID
    interview_link_id: uuid.UUID


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


def _forbidden(detail: str) -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def _invalid_interview_link() -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Interview link is invalid")


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


def create_candidate_access_token(
    *,
    candidate_id: uuid.UUID,
    interview_link_id: uuid.UUID,
    settings: Settings | None = None,
    now: int | None = None,
) -> str:
    """Выпускает короткий JWT для кандидата после обмена magic link."""
    settings = settings or get_settings()
    issued_at = now or int(time.time())
    payload = {
        "sub": str(candidate_id),
        "link_id": str(interview_link_id),
        "kind": "candidate_session",
        "iat": issued_at,
        "exp": issued_at + settings.candidate_jwt_access_token_ttl_seconds,
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


def decode_candidate_access_token(
    token: str, settings: Settings | None = None
) -> CandidateSession:
    """Проверяет кандидатский JWT и восстанавливает candidate/link ids."""
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
        candidate_id = uuid.UUID(str(payload["sub"]))
        interview_link_id = uuid.UUID(str(payload["link_id"]))
        kind = str(payload["kind"])
        expires_at = int(payload["exp"])
    except (KeyError, ValueError, json.JSONDecodeError):
        raise _invalid_credentials() from None

    if kind != "candidate_session" or expires_at < int(time.time()):
        raise _invalid_credentials()

    return CandidateSession(candidate_id=candidate_id, interview_link_id=interview_link_id)


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


def ensure_topic_status_change_allowed(user: CurrentUser, skill_type: SkillType) -> None:
    """Проверяет матрицу прав изменения статуса топика."""
    if user.role == AppRole.RECRUITER:
        raise _forbidden("Recruiter cannot change topic statuses")

    if skill_type == SkillType.HARD and user.role != AppRole.TECH_SPECIALIST:
        raise _forbidden("Only technical specialist can change hard-topic status")

    if skill_type == SkillType.SOFT and user.role != AppRole.HIRING_MANAGER:
        raise _forbidden("Only hiring manager can change soft-topic status")


def ensure_interview_link_issue_allowed(user: CurrentUser) -> None:
    """Проверяет право выпуска ссылки интервью."""
    if user.role != AppRole.RECRUITER:
        raise _forbidden("Only recruiter can issue interview links")


async def exchange_interview_link_token(
    session: AsyncSession,
    token: str,
    *,
    settings: Settings | None = None,
    now: int | None = None,
) -> CandidateSession:
    """Обменивает валидную magic link на короткую JWT-сессию кандидата."""
    settings = settings or get_settings()
    link = await session.scalar(
        select(InterviewLink).where(InterviewLink.token == token)
    )
    if link is None:
        raise _invalid_interview_link()

    current_ts = now or int(time.time())
    if link.revoked or link.used_at is not None:
        raise _invalid_interview_link()

    if int(link.expires_at.timestamp()) < current_ts:
        raise _invalid_interview_link()

    return CandidateSession(candidate_id=link.candidate_id, interview_link_id=link.id)


def get_candidate_session(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    settings: Settings = Depends(get_settings),
) -> CandidateSession:
    """Dependency FastAPI: валидирует Bearer JWT кандидата."""
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _invalid_credentials()
    return decode_candidate_access_token(credentials.credentials, settings=settings)
