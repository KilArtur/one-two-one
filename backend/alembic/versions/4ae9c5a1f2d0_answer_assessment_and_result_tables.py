"""answer, assessment, status log and interview result tables

Таблицы ответа кандидата, оценки топика, append-only аудита смены статуса
и итогового результата интервью (раздел 5 PRD).

Revision ID: 4ae9c5a1f2d0
Revises: a7feac956a32
Create Date: 2026-09-04 20:40:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "4ae9c5a1f2d0"
down_revision: str | Sequence[str] | None = "a7feac956a32"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENUM_NAMES = (
    "interview_recommendation",
    "reviewer_role",
    "assessment_confidence",
    "assessment_status",
    "answer_processing_status",
)


def upgrade() -> None:
    """Применяет ревизию."""
    op.create_table(
        "answer",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("question_id", sa.Uuid(), nullable=False),
        sa.Column("video_url", sa.String(length=1024), nullable=True),
        sa.Column("audio_url", sa.String(length=1024), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=True),
        sa.Column("transcript_segments", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("duration_sec", sa.Integer(), nullable=True),
        sa.Column("skipped", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column(
            "technically_lost", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column(
            "processing_status",
            sa.Enum(
                "recorded",
                "transcribing",
                "analyzing",
                "ready",
                "error",
                name="answer_processing_status",
            ),
            server_default=sa.text("'recorded'"),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["question_id"], ["question.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_answer_question_id"), "answer", ["question_id"], unique=False)
    op.create_table(
        "topic_assessment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("topic_id", sa.Uuid(), nullable=False),
        sa.Column(
            "system_status",
            sa.Enum(
                "confirmed",
                "needs_check",
                "not_confirmed",
                "out_of_scope",
                name="assessment_status",
            ),
            nullable=False,
        ),
        sa.Column(
            "current_status",
            sa.Enum(
                "confirmed",
                "needs_check",
                "not_confirmed",
                "out_of_scope",
                name="assessment_status",
            ),
            nullable=False,
        ),
        sa.Column(
            "confidence",
            sa.Enum("high", "medium", "low", name="assessment_confidence"),
            nullable=False,
        ),
        sa.Column("signals", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("evidence", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("reasoning_summary", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(), nullable=True),
        sa.Column("reviewer_comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["topic.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("candidate_id", "topic_id", name="uq_topic_assessment_candidate_topic"),
    )
    op.create_index(
        op.f("ix_topic_assessment_candidate_id"),
        "topic_assessment",
        ["candidate_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_topic_assessment_topic_id"),
        "topic_assessment",
        ["topic_id"],
        unique=False,
    )
    op.create_table(
        "status_change_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("assessment_id", sa.Uuid(), nullable=False),
        sa.Column("author_id", sa.Uuid(), nullable=False),
        sa.Column(
            "author_role",
            sa.Enum(
                "recruiter",
                "technical_specialist",
                "hiring_manager",
                name="reviewer_role",
            ),
            nullable=False,
        ),
        sa.Column(
            "old_status",
            sa.Enum(
                "confirmed",
                "needs_check",
                "not_confirmed",
                "out_of_scope",
                name="assessment_status",
            ),
            nullable=False,
        ),
        sa.Column(
            "new_status",
            sa.Enum(
                "confirmed",
                "needs_check",
                "not_confirmed",
                "out_of_scope",
                name="assessment_status",
            ),
            nullable=False,
        ),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["assessment_id"], ["topic_assessment.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_status_change_log_assessment_id"),
        "status_change_log",
        ["assessment_id"],
        unique=False,
    )
    op.create_table(
        "interview_result",
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("confirmed_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("needs_check_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("not_confirmed_count", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("mandatory_coverage", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column("desired_coverage", sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column(
            "recommendation",
            sa.Enum("fit", "additional_check", "not_fit", name="interview_recommendation"),
            nullable=False,
        ),
        sa.Column("vacancy_version", sa.Integer(), nullable=False),
        sa.Column("model_version", sa.String(length=255), nullable=False),
        sa.Column("prompt_version", sa.String(length=255), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["candidate_id"], ["candidate.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("candidate_id"),
    )


def downgrade() -> None:
    """Откатывает ревизию."""
    op.drop_table("interview_result")
    op.drop_index(op.f("ix_status_change_log_assessment_id"), table_name="status_change_log")
    op.drop_table("status_change_log")
    op.drop_index(op.f("ix_topic_assessment_topic_id"), table_name="topic_assessment")
    op.drop_index(op.f("ix_topic_assessment_candidate_id"), table_name="topic_assessment")
    op.drop_table("topic_assessment")
    op.drop_index(op.f("ix_answer_question_id"), table_name="answer")
    op.drop_table("answer")
    for enum_name in ENUM_NAMES:
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
