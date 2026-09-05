"""Recover pending recordings and submitted interviews from durable database state."""

import asyncio
import logging

from celery import Celery
from sqlalchemy import select

from app.db import dispose_engine
from app.db.session import get_sessionmaker
from app.models.answer import Answer, AnswerProcessingStatus
from app.models.candidate import Candidate, CandidateStatus
from app.services.interview_result import assemble_interview_result
from app.services.pipeline import process_answer
from app.services.transcription import transcribe_answer

logger = logging.getLogger(__name__)


async def process_pending() -> dict[str, int]:
    """Transcribe recordings early; freeze topic assessments after final submission."""
    processed = 0
    try:
        async with get_sessionmaker()() as session:
            answer_ids = list(
                await session.scalars(
                    select(Answer.id)
                    .where(
                        Answer.processing_status.in_(
                            [
                                AnswerProcessingStatus.RECORDED,
                                AnswerProcessingStatus.TRANSCRIBING,
                            ]
                        )
                    )
                    .order_by(Answer.created_at)
                    .limit(20)
                )
            )
            for answer_id in answer_ids:
                try:
                    await transcribe_answer(session, answer_id)
                except Exception:
                    await session.rollback()
                    logger.exception("Transcription failed for answer %s", answer_id)
            candidate_ids = list(
                await session.scalars(
                    select(Candidate.id).where(Candidate.status == CandidateStatus.SUBMITTED)
                )
            )
            for candidate_id in candidate_ids:
                try:
                    answers = list(
                        await session.scalars(
                            select(Answer)
                            .where(Answer.candidate_id == candidate_id)
                            .order_by(Answer.created_at)
                        )
                    )
                    for answer in answers:
                        await process_answer(session, answer.id)
                    await assemble_interview_result(session, candidate_id)
                    candidate = await session.get(Candidate, candidate_id)
                    candidate.status = CandidateStatus.PROCESSED
                    await session.commit()
                    processed += 1
                except Exception:
                    await session.rollback()
                    logger.exception("Processing failed for candidate %s", candidate_id)
        return {"processed": processed}
    finally:
        await dispose_engine()


def register_pending_task(app: Celery) -> None:
    """Register a periodic recovery task; use a single local worker."""

    @app.task(name="app.process_pending", ignore_result=True)
    def process_pending_task() -> dict[str, int]:
        return asyncio.run(process_pending())
