"""candidate, interview link and question tables

Таблицы кандидата, персональной ссылки на интервью и вопроса с self-FK
parent_question_id для уточнений (раздел 5 PRD).

Revision ID: a7feac956a32
Revises: f7db7e0c8e3e
Create Date: 2026-09-04 20:03:17.031003
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "a7feac956a32"
down_revision: str | Sequence[str] | None = "f7db7e0c8e3e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENUM_NAMES = ("question_pattern", "question_type", "candidate_status")


def upgrade() -> None:
    """Применяет ревизию."""
    op.create_table(
        "candidate",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vacancy_id", sa.Uuid(), nullable=False),
        sa.Column("resume_text", sa.Text(), nullable=True),
        sa.Column("resume_file_url", sa.String(length=1024), nullable=True),
        sa.Column("consent_given_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "invited",
                "in_progress",
                "submitted",
                "processed",
                "reviewed",
                name="candidate_status",
            ),
            server_default=sa.text("'invited'"),
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
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancy.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_candidate_vacancy_id"), "candidate", ["vacancy_id"], unique=False)
    op.create_table(
        "interview_link",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("candidate_id", sa.Uuid(), nullable=False),
        sa.Column("token", sa.String(length=255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked", sa.Boolean(), server_default=sa.text("false"), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_interview_link_candidate_id"), "interview_link", ["candidate_id"], unique=False
    )
    op.create_index(op.f("ix_interview_link_token"), "interview_link", ["token"], unique=True)
    op.create_table(
        "question",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("topic_id", sa.Uuid(), nullable=False),
        sa.Column(
            "type",
            sa.Enum("core", "personal", "follow_up", name="question_type"),
            nullable=False,
        ),
        sa.Column(
            "pattern",
            sa.Enum("technical", "experience", "reasoning", name="question_pattern"),
            nullable=False,
        ),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("source_reason", sa.Text(), nullable=True),
        sa.Column(
            "reviewed_by_expert", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("parent_question_id", sa.Uuid(), nullable=True),
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
        sa.ForeignKeyConstraint(["parent_question_id"], ["question.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["topic_id"], ["topic.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_question_parent_question_id"), "question", ["parent_question_id"], unique=False
    )
    op.create_index(op.f("ix_question_topic_id"), "question", ["topic_id"], unique=False)


def downgrade() -> None:
    """Откатывает ревизию."""
    op.drop_index(op.f("ix_question_topic_id"), table_name="question")
    op.drop_index(op.f("ix_question_parent_question_id"), table_name="question")
    op.drop_table("question")
    op.drop_index(op.f("ix_interview_link_token"), table_name="interview_link")
    op.drop_index(op.f("ix_interview_link_candidate_id"), table_name="interview_link")
    op.drop_table("interview_link")
    op.drop_index(op.f("ix_candidate_vacancy_id"), table_name="candidate")
    op.drop_table("candidate")
    for enum_name in ENUM_NAMES:
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
