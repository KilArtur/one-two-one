"""Адаптивные уточняющие вопросы (M4) на LangGraph: решение об уточнении по Р12.

Решение принимается синхронно между ответами быстрым LLM на коротком контексте (топик +
ответы по нему). Граф состояний LangGraph описывает ход: проверка лимита → решение →
уточнение/закрытие. Не задаём уточнение по 4 условиям Р12 (статус определён, лимит,
нет новой информации, нет опыта); максимум 2 уточнения; сбой генерации → топик закрывается.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.llm import LangChainLLMClient, LLMClientError, get_llm_client
from app.models.answer import Answer
from app.models.question import Question, QuestionPattern, QuestionType
from app.models.topic import Topic
from app.prompts import load_prompt
from app.schemas.assessment import FollowupDecisionLLM

FOLLOWUP_PROMPT = "followup_decision"
FOLLOWUP_PROMPT_VERSION = "followup-decision-v1"
MAX_FOLLOWUPS = 2


@dataclass(slots=True, frozen=True)
class FollowupResult:
    """Итог решения об уточнении."""

    ask: bool
    reason: str
    question: Question | None = None


class _State(TypedDict, total=False):
    topic_title: str
    requirement_description: str
    core_question: str
    answers_text: str
    followups_count: int
    ask: bool
    followup_question: str
    reason: str
    decided: bool


def build_followup_graph(llm_client: LangChainLLMClient):
    """Строит LangGraph-граф решения об уточнении (гейт лимита → быстрый LLM → Р12)."""

    def gate(state: _State) -> _State:
        if state["followups_count"] >= MAX_FOLLOWUPS:
            return {"ask": False, "reason": "limit_reached", "decided": True}
        return {"decided": False}

    async def decide(state: _State) -> _State:
        prompt = load_prompt(FOLLOWUP_PROMPT).format(
            topic_title=state["topic_title"],
            requirement_description=state["requirement_description"] or "—",
            core_question=state["core_question"],
            answers=state["answers_text"] or "—",
        )
        try:
            result = await llm_client.generate_structured(
                prompt,
                schema=FollowupDecisionLLM,
                prompt_version=FOLLOWUP_PROMPT_VERSION,
                use_fast_model=True,
            )
        except LLMClientError:
            return {"ask": False, "reason": "llm_error", "followup_question": ""}

        verdict: FollowupDecisionLLM = result.content
        is_first = state["followups_count"] == 0
        ask = (
            verdict.needs_clarification
            and not verdict.answer_sufficient
            and not verdict.explicit_no_experience
            and (verdict.adds_new_information or is_first)
            and bool(verdict.followup_question.strip())
        )
        if ask:
            reason = "clarification_needed"
        elif verdict.answer_sufficient:
            reason = "status_determined"
        elif verdict.explicit_no_experience:
            reason = "no_experience"
        elif not verdict.adds_new_information and not is_first:
            reason = "no_new_information"
        else:
            reason = "no_clarification_needed"
        return {
            "ask": ask,
            "followup_question": verdict.followup_question.strip(),
            "reason": reason,
        }

    graph = StateGraph(_State)
    graph.add_node("gate", gate)
    graph.add_node("decide", decide)
    graph.add_edge(START, "gate")
    graph.add_conditional_edges(
        "gate",
        lambda state: END if state["decided"] else "decide",
        {END: END, "decide": "decide"},
    )
    graph.add_edge("decide", END)
    return graph.compile()


async def _topic_answers_text(
    session: AsyncSession, candidate_id: uuid.UUID, topic_id: uuid.UUID
) -> str:
    rows = list(
        await session.scalars(
            select(Answer)
            .join(Question, Question.id == Answer.question_id)
            .where(Answer.candidate_id == candidate_id, Question.topic_id == topic_id)
            .order_by(Answer.created_at)
        )
    )
    lines = []
    for index, answer in enumerate(rows, start=1):
        if answer.skipped:
            body = "[вопрос пропущен]"
        elif answer.transcript:
            body = answer.transcript
        else:
            body = "[нет транскрипта]"
        lines.append(f"{index}. {body}")
    return "\n".join(lines)


async def decide_followup(
    session: AsyncSession,
    candidate_id: uuid.UUID,
    topic_id: uuid.UUID,
    *,
    llm_client: LangChainLLMClient | None = None,
) -> FollowupResult:
    """Решает, задать ли уточнение по топику, и создаёт follow_up-вопрос при необходимости."""
    llm_client = llm_client or get_llm_client()
    topic = await session.get(Topic, topic_id)
    if topic is None:
        return FollowupResult(ask=False, reason="topic_not_found")

    core_question = await session.scalar(
        select(Question).where(
            Question.topic_id == topic_id, Question.type == QuestionType.CORE
        )
    )
    if core_question is None:
        return FollowupResult(ask=False, reason="core_question_missing")

    followups_count = (
        await session.scalar(
            select(func.count())
            .select_from(Question)
            .where(
                Question.topic_id == topic_id,
                Question.type == QuestionType.FOLLOW_UP,
                Question.parent_question_id == core_question.id,
            )
        )
    ) or 0

    graph = build_followup_graph(llm_client)
    state: _State = await graph.ainvoke(
        {
            "topic_title": topic.title,
            "requirement_description": topic.requirement_description or "",
            "core_question": core_question.text,
            "answers_text": await _topic_answers_text(session, candidate_id, topic_id),
            "followups_count": followups_count,
        }
    )

    if not state.get("ask"):
        return FollowupResult(ask=False, reason=state.get("reason", "no_clarification_needed"))

    question = Question(
        topic_id=topic_id,
        type=QuestionType.FOLLOW_UP,
        pattern=QuestionPattern.REASONING,
        text=state["followup_question"],
        parent_question_id=core_question.id,
    )
    session.add(question)
    await session.commit()
    await session.refresh(question)
    return FollowupResult(ask=True, reason="clarification_needed", question=question)
