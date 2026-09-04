"""Add answer, topic_assessment, status_change_log, interview_result (PRD §5).

Revision ID: 0004_answer_assessment
Revises: 0003_candidate_question
Create Date: 2026-09-04

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004_answer_assessment"
down_revision: str | None = "0003_candidate_question"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

processing_status = postgresql.ENUM(
    "recorded",
    "transcribing",
    "analyzing",
    "ready",
    "error",
    name="processing_status",
    create_type=False,
)
topic_status = postgresql.ENUM(
    "confirmed",
    "needs_check",
    "not_confirmed",
    "out_of_scope",
    name="topic_status",
    create_type=False,
)
confidence = postgresql.ENUM(
    "high",
    "medium",
    "low",
    name="confidence",
    create_type=False,
)
author_role = postgresql.ENUM(
    "system",
    "recruiter",
    "tech_specialist",
    "hiring_manager",
    name="author_role",
    create_type=False,
)
recommendation = postgresql.ENUM(
    "suitable",
    "not_suitable",
    "needs_additional_check",
    name="recommendation",
    create_type=False,
)


def upgrade() -> None:
    """Create answer / assessment / log / result tables and related enums."""
    processing_status.create(op.get_bind(), checkfirst=True)
    topic_status.create(op.get_bind(), checkfirst=True)
    confidence.create(op.get_bind(), checkfirst=True)
    author_role.create(op.get_bind(), checkfirst=True)
    recommendation.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "answer",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("question_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("video_url", sa.String(length=2048), nullable=True),
        sa.Column("audio_url", sa.String(length=2048), nullable=True),
        sa.Column("transcript", sa.Text(), nullable=False),
        sa.Column(
            "transcript_segments",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("duration_sec", sa.Integer(), nullable=True),
        sa.Column(
            "skipped",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column(
            "technically_lost",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("processing_status", processing_status, nullable=False),
        sa.ForeignKeyConstraint(["question_id"], ["question.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_answer_question_id"),
        "answer",
        ["question_id"],
        unique=False,
    )

    op.create_table(
        "topic_assessment",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("system_status", topic_status, nullable=False),
        sa.Column("current_status", topic_status, nullable=False),
        sa.Column("confidence", confidence, nullable=False),
        sa.Column(
            "signals",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'{}'::jsonb"),
            nullable=False,
        ),
        sa.Column(
            "evidence",
            postgresql.JSONB(astext_type=sa.Text()),
            server_default=sa.text("'[]'::jsonb"),
            nullable=False,
        ),
        sa.Column("reasoning_summary", sa.Text(), nullable=False),
        sa.Column("reviewed_by", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("reviewer_comment", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidate.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(["topic_id"], ["topic.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "candidate_id",
            "topic_id",
            name="uq_topic_assessment_candidate_topic",
        ),
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
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("assessment_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("author_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("author_role", author_role, nullable=False),
        sa.Column("old_status", topic_status, nullable=False),
        sa.Column("new_status", topic_status, nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["assessment_id"],
            ["topic_assessment.id"],
            ondelete="CASCADE",
        ),
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
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("confirmed_count", sa.Integer(), nullable=False),
        sa.Column("needs_check_count", sa.Integer(), nullable=False),
        sa.Column("not_confirmed_count", sa.Integer(), nullable=False),
        sa.Column(
            "mandatory_coverage",
            sa.Numeric(precision=5, scale=4),
            nullable=True,
        ),
        sa.Column(
            "desired_coverage",
            sa.Numeric(precision=5, scale=4),
            nullable=True,
        ),
        sa.Column("recommendation", recommendation, nullable=False),
        sa.Column("vacancy_version", sa.Integer(), nullable=False),
        sa.Column("model_version", sa.String(length=128), nullable=False),
        sa.Column("prompt_version", sa.String(length=128), nullable=False),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidate.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("candidate_id"),
    )


def downgrade() -> None:
    """Drop assessment-related tables and enums."""
    op.drop_table("interview_result")
    op.drop_index(
        op.f("ix_status_change_log_assessment_id"),
        table_name="status_change_log",
    )
    op.drop_table("status_change_log")
    op.drop_index(op.f("ix_topic_assessment_topic_id"), table_name="topic_assessment")
    op.drop_index(
        op.f("ix_topic_assessment_candidate_id"),
        table_name="topic_assessment",
    )
    op.drop_table("topic_assessment")
    op.drop_index(op.f("ix_answer_question_id"), table_name="answer")
    op.drop_table("answer")
    recommendation.drop(op.get_bind(), checkfirst=True)
    author_role.drop(op.get_bind(), checkfirst=True)
    confidence.drop(op.get_bind(), checkfirst=True)
    topic_status.drop(op.get_bind(), checkfirst=True)
    processing_status.drop(op.get_bind(), checkfirst=True)
