"""Транскрипты кандидата с цитатами только из оценки соответствующего топика."""

import uuid

from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Answer, Candidate, Question, Topic, TopicAssessment


class TranscriptSegment(BaseModel):
    text: str
    start: float = Field(ge=0, allow_inf_nan=False)
    end: float = Field(ge=0, allow_inf_nan=False)


class TranscriptRead(BaseModel):
    answer_id: uuid.UUID
    question_id: uuid.UUID
    topic_id: uuid.UUID
    question: str
    transcript: str | None
    segments: list[TranscriptSegment]
    quotes: list[str]
    processing_status: str
    skipped: bool
    technically_lost: bool


async def load_transcripts(
    session: AsyncSession, candidate_id: uuid.UUID, topic_id: uuid.UUID | None = None
) -> list[TranscriptRead]:
    candidate = await session.get(Candidate, candidate_id)
    if candidate is None:
        raise HTTPException(404, "Candidate not found")
    query = (
        select(Answer, Question)
        .join(Question)
        .join(Topic)
        .where(Answer.candidate_id == candidate_id, Topic.vacancy_id == candidate.vacancy_id)
        .order_by(Topic.order, Question.created_at, Question.id)
    )
    if topic_id is not None:
        topic = await session.get(Topic, topic_id)
        if topic is None or topic.vacancy_id != candidate.vacancy_id:
            raise HTTPException(404, "Topic not found")
        query = query.where(Topic.id == topic_id)
    assessments = await session.scalars(
        select(TopicAssessment).where(TopicAssessment.candidate_id == candidate_id)
    )
    evidence = {a.topic_id: a.evidence or [] for a in assessments}
    results = []
    for answer, question in (await session.execute(query)).all():
        segments = []
        for raw in answer.transcript_segments or []:
            try:
                segment = TranscriptSegment.model_validate(raw)
            except ValidationError:
                continue
            if segment.end >= segment.start:
                segments.append(segment)
        quotes = (
            list(
                dict.fromkeys(
                    e["quote"]
                    for e in evidence.get(question.topic_id, [])
                    if isinstance(e, dict)
                    and str(e.get("question_id")) == str(question.id)
                    and isinstance(e.get("quote"), str)
                    and e["quote"].strip()
                )
            )
            if answer.transcript or segments
            else []
        )
        results.append(
            TranscriptRead(
                answer_id=answer.id,
                question_id=question.id,
                topic_id=question.topic_id,
                question=question.text,
                transcript=answer.transcript,
                segments=segments,
                quotes=quotes,
                processing_status=answer.processing_status.value,
                skipped=answer.skipped,
                technically_lost=answer.technically_lost,
            )
        )
    return results
