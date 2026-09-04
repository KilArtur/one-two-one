"""HTTP-роутеры приложения."""

from app.api.auth import router as auth_router
from app.api.vacancies import router as vacancies_router

__all__ = ["auth_router", "vacancies_router"]
