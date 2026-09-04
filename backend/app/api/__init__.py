"""HTTP-роутеры приложения."""

from app.api.vacancies import router as vacancies_router

__all__ = ["vacancies_router"]
