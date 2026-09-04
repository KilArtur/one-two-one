"""HTTP-роутеры приложения."""

from app.api.auth import router as auth_router
from app.api.rbac import router as rbac_router
from app.api.vacancies import router as vacancies_router

__all__ = ["auth_router", "rbac_router", "vacancies_router"]
