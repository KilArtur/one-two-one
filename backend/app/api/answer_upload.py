"""API загрузки раздельных дорожек ответа с подтверждением сохранения."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, UploadFile
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.integrations.storage import S3StorageClient, S3StorageError, get_s3_storage_client
from app.models.answer import Answer
from app.models.candidate import Candidate
from app.services import answer_upload as service
from app.services.consent import require_candidate_consent

router = APIRouter(prefix="/candidate-interview", tags=["answer-upload"])
SessionDep = Annotated[AsyncSession, Depends(get_db)]
CandidateDep = Annotated[Candidate, Depends(require_candidate_consent)]
StorageDep = Annotated[S3StorageClient, Depends(get_s3_storage_client)]


class StartRequest(BaseModel):
    upload_id: uuid.UUID


class UploadRead(BaseModel):
    id: uuid.UUID
    video_chunks: int
    audio_chunks: int
    saved: bool


class CompleteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    video_chunks: int = Field(ge=1, le=300)
    audio_chunks: int = Field(ge=1, le=300)
    duration_sec: int = Field(ge=1, le=120)


class SavedAnswerRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: uuid.UUID
    question_id: uuid.UUID
    duration_sec: int
    processing_status: str


@router.post("/questions/{question_id}/uploads", response_model=UploadRead)
async def start(
    question_id: uuid.UUID, data: StartRequest, candidate: CandidateDep, session: SessionDep
) -> UploadRead:
    upload = await service.start_upload(session, candidate, question_id, data.upload_id)
    return UploadRead(
        id=upload.id,
        video_chunks=len(upload.manifest["video"]["parts"]),
        audio_chunks=len(upload.manifest["audio"]["parts"]),
        saved=await session.get(Answer, upload.id) is not None,
    )


@router.put("/uploads/{upload_id}/{kind}/{index}")
async def chunk(
    upload_id: uuid.UUID,
    kind: service.TrackKind,
    index: Annotated[int, Path(ge=0, le=299)],
    file: UploadFile,
    candidate: CandidateDep,
    session: SessionDep,
    storage: StorageDep,
) -> dict[str, int]:
    upload = await service.locked_upload(session, candidate.id, upload_id)
    try:
        data = await file.read(service.MAX_CHUNK_BYTES + 1)
        await service.put_chunk(
            session, upload, storage, kind, index, data, file.content_type or ""
        )
    except S3StorageError:
        raise HTTPException(503, "Chunk storage is unavailable") from None
    finally:
        await file.close()
    return {"index": index}


@router.post("/uploads/{upload_id}/complete", response_model=SavedAnswerRead)
async def complete(
    upload_id: uuid.UUID,
    data: CompleteRequest,
    candidate: CandidateDep,
    session: SessionDep,
    storage: StorageDep,
) -> Answer:
    upload = await service.locked_upload(session, candidate.id, upload_id)
    try:
        return await service.complete_upload(session, upload, storage, **data.model_dump())
    except S3StorageError:
        raise HTTPException(503, "Recording assembly is unavailable") from None
