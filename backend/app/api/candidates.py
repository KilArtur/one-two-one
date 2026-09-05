"""API досрочного удаления данных кандидата по запросу (Р18)."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.integrations.storage import S3StorageClient, get_s3_storage_client
from app.services.auth import CurrentUser, get_current_user
from app.services.retention import purge_candidate

router = APIRouter(prefix="/candidates", tags=["candidates"])

SessionDep = Annotated[AsyncSession, Depends(get_db)]
CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
StorageDep = Annotated[S3StorageClient, Depends(get_s3_storage_client)]


class PurgeRequest(BaseModel):
    reason: str = Field(default="on_request", min_length=1, max_length=500)


class PurgeResult(BaseModel):
    candidate_id: uuid.UUID
    reason: str
    details: dict | None


@router.post("/{candidate_id}/purge", response_model=PurgeResult)
async def purge_candidate_data(
    candidate_id: uuid.UUID,
    data: PurgeRequest,
    current_user: CurrentUserDep,
    session: SessionDep,
    storage: StorageDep,
) -> PurgeResult:
    """Досрочно удаляет ПДн кандидата и логирует факт удаления."""
    log = await purge_candidate(
        session, storage, candidate_id, reason=data.reason, force_log=True
    )
    if log is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    return PurgeResult(candidate_id=candidate_id, reason=log.reason, details=log.details)
