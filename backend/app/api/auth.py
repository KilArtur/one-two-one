"""JWT-аутентификация внутренних ролей."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from app.config import Settings, get_settings
from app.schemas.auth import AuthTokenRequest, AuthTokenResponse, CurrentUserRead
from app.services.auth import (
    CurrentUser,
    authenticate_internal_user,
    create_access_token,
    get_current_user,
)

router = APIRouter(prefix="/auth", tags=["auth"])

SettingsDep = Annotated[Settings, Depends(get_settings)]
CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]


@router.post("/token", response_model=AuthTokenResponse)
async def login_for_access_token(
    data: AuthTokenRequest,
    settings: SettingsDep,
) -> AuthTokenResponse:
    """Выдаёт JWT для внутреннего пользователя с ролью в claims."""
    user = authenticate_internal_user(
        username=data.username,
        password=data.password,
        role=data.role,
        settings=settings,
    )
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username, password, or role",
        )
    return AuthTokenResponse(
        access_token=create_access_token(
            username=user.username,
            role=user.role,
            settings=settings,
        )
    )


@router.get("/me", response_model=CurrentUserRead)
async def get_me(current_user: CurrentUserDep) -> CurrentUserRead:
    """Возвращает пользователя из валидного Bearer token."""
    return CurrentUserRead(username=current_user.username, role=current_user.role.value)
