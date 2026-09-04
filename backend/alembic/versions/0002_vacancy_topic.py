"""Add vacancy and topic tables (PRD §5).

Revision ID: 0002_vacancy_topic
Revises: 0001_baseline
Create Date: 2026-09-04

"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0002_vacancy_topic"
down_revision: str | None = "0001_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

vacancy_grade = postgresql.ENUM(
    "junior",
    "middle",
    "middle+",
    "senior",
    name="vacancy_grade",
    create_type=False,
)
vacancy_status = postgresql.ENUM(
    "draft",
    "active",
    "archived",
    name="vacancy_status",
    create_type=False,
)
skill_type = postgresql.ENUM(
    "hard",
    "soft",
    name="skill_type",
    create_type=False,
)
importance = postgresql.ENUM(
    "mandatory",
    "desired",
    name="importance",
    create_type=False,
)


def upgrade() -> None:
    """Create vacancy / topic tables and related enums."""
    vacancy_grade.create(op.get_bind(), checkfirst=True)
    vacancy_status.create(op.get_bind(), checkfirst=True)
    skill_type.create(op.get_bind(), checkfirst=True)
    importance.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "vacancy",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("grade", vacancy_grade, nullable=False),
        sa.Column("tasks", sa.Text(), nullable=False),
        sa.Column(
            "stop_factors",
            postgresql.ARRAY(sa.Text()),
            server_default="{}",
            nullable=False,
        ),
        sa.Column("specialist_profile", sa.Text(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("status", vacancy_status, nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "topic",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("vacancy_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("title", sa.String(length=512), nullable=False),
        sa.Column("skill_type", skill_type, nullable=False),
        sa.Column("importance", importance, nullable=False),
        sa.Column("requirement_description", sa.Text(), nullable=False),
        sa.Column("depth_expectations", sa.Text(), nullable=False),
        sa.Column(
            "verifiable_by_interview",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("order", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["vacancy_id"], ["vacancy.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_topic_vacancy_id"), "topic", ["vacancy_id"], unique=False)


def downgrade() -> None:
    """Drop vacancy / topic tables and related enums."""
    op.drop_index(op.f("ix_topic_vacancy_id"), table_name="topic")
    op.drop_table("topic")
    op.drop_table("vacancy")
    importance.drop(op.get_bind(), checkfirst=True)
    skill_type.drop(op.get_bind(), checkfirst=True)
    vacancy_status.drop(op.get_bind(), checkfirst=True)
    vacancy_grade.drop(op.get_bind(), checkfirst=True)
