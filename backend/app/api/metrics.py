"""Продуктовые метрики для внутренних ролей."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.services.auth import CurrentUser, get_current_user
from app.services.product_metrics import ProductMetrics, load_metrics

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("/product", response_model=ProductMetrics)
async def product_metrics(
    user: Annotated[CurrentUser, Depends(get_current_user)],
    session: Annotated[AsyncSession, Depends(get_db)],
    vacancy_id: uuid.UUID | None = None,
) -> ProductMetrics:
    return await load_metrics(session, vacancy_id)
