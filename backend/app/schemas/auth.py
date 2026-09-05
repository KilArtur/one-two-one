"""Схемы JWT-аутентификации внутренних ролей."""

from __future__ import annotations

from pydantic import BaseModel, Field


class AuthTokenRequest(BaseModel):
    """Запрос на выпуск access token для внутреннего пользователя."""

    username: str = Field(min_length=1, max_length=255)
    password: str = Field(min_length=1, max_length=255)
    role: str


class AuthTokenResponse(BaseModel):
    """Ответ login-эндпоинта с Bearer access token."""

    access_token: str
    token_type: str = "bearer"


class CurrentUserRead(BaseModel):
    """Текущий пользователь, восстановленный из JWT."""

    username: str
    role: str
