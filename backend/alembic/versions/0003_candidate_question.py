"""Add candidate, interview_link, and question tables (PRD §5).

Revision ID: 0003_candidate_question
Revises: 0002_vacancy_topic
Create Date: 2026-09-04

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003_candidate_question"
down_revision: str | None = "0002_vacancy_topic"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

candidate_status = postgresql.ENUM(
    "invited",
    "in_progress",
    "submitted",
    "processed",
    "reviewed",
    name="candidate_status",
    create_type=False,
)
question_type = postgresql.ENUM(
    "core",
    "personal",
    "follow_up",
    name="question_type",
    create_type=False,
)
question_pattern = postgresql.ENUM(
    "technical",
    "experience",
    "reasoning",
    name="question_pattern",
    create_type=False,
)


def upgrade() -> None:
    """Create candidate / interview_link / question tables and related enums."""
    candidate_status.create(op.get_bind(), checkfirst=True)
    question_type.create(op.get_bind(), checkfirst=True)
    question_pattern.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "candidate",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vacancy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("resume_text", sa.Text(), nullable=False),
        sa.Column("resume_file_url", sa.String(length=2048), nullable=True),
        sa.Column("consent_given_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", candidate_status, nullable=False),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancy.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_candidate_vacancy_id"),
        "candidate",
        ["vacancy_id"],
        unique=False,
    )

    op.create_table(
        "interview_link",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("candidate_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("token", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "revoked",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["candidate_id"],
            ["candidate.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token"),
    )
    op.create_index(
        op.f("ix_interview_link_candidate_id"),
        "interview_link",
        ["candidate_id"],
        unique=False,
    )

    op.create_table(
        "question",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("topic_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", question_type, nullable=False),
        sa.Column("pattern", question_pattern, nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source_reason", sa.Text(), nullable=False),
        sa.Column(
            "reviewed_by_expert",
            sa.Boolean(),
            server_default=sa.text("false"),
            nullable=False,
        ),
        sa.Column("parent_question_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.ForeignKeyConstraint(["topic_id"], ["topic.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["parent_question_id"],
            ["question.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_question_topic_id"),
        "question",
        ["topic_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_question_parent_question_id"),
        "question",
        ["parent_question_id"],
        unique=False,
    )


def downgrade() -> None:
    """Drop candidate / interview_link / question tables and related enums."""
    op.drop_index(op.f("ix_question_parent_question_id"), table_name="question")
    op.drop_index(op.f("ix_question_topic_id"), table_name="question")
    op.drop_table("question")
    op.drop_index(
        op.f("ix_interview_link_candidate_id"),
        table_name="interview_link",
    )
    op.drop_table("interview_link")
    op.drop_index(op.f("ix_candidate_vacancy_id"), table_name="candidate")
    op.drop_table("candidate")
    question_pattern.drop(op.get_bind(), checkfirst=True)
    question_type.drop(op.get_bind(), checkfirst=True)
    candidate_status.drop(op.get_bind(), checkfirst=True)
