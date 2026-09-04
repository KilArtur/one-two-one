"""vacancy and topic tables

Таблицы вакансии и топиков требований с FK topic -> vacancy (раздел 5 PRD).

Revision ID: f7db7e0c8e3e
Revises: 11d73faaed8f
Create Date: 2026-09-04 19:58:24.780019
"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "f7db7e0c8e3e"
down_revision: str | Sequence[str] | None = "11d73faaed8f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ENUM_NAMES = ("topic_importance", "topic_skill_type", "vacancy_status", "vacancy_grade")


def upgrade() -> None:
    """Применяет ревизию."""
    op.create_table(
        "vacancy",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column(
            "grade",
            sa.Enum("junior", "middle", "middle+", "senior", name="vacancy_grade"),
            nullable=False,
        ),
        sa.Column("tasks", sa.Text(), nullable=True),
        sa.Column(
            "stop_factors",
            sa.ARRAY(sa.Text()).with_variant(sa.JSON(), "sqlite"),
            server_default=sa.text("'{}'"),
            nullable=False,
        ),
        sa.Column("specialist_profile", sa.Text(), nullable=True),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "active", "archived", name="vacancy_status"),
            server_default=sa.text("'draft'"),
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
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_table(
        "topic",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("vacancy_id", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("skill_type", sa.Enum("hard", "soft", name="topic_skill_type"), nullable=False),
        sa.Column(
            "importance",
            sa.Enum("mandatory", "desired", name="topic_importance"),
            nullable=False,
        ),
        sa.Column("requirement_description", sa.Text(), nullable=True),
        sa.Column("depth_expectations", sa.Text(), nullable=True),
        sa.Column(
            "verifiable_by_interview",
            sa.Boolean(),
            server_default=sa.text("true"),
            nullable=False,
        ),
        sa.Column("order", sa.Integer(), server_default=sa.text("0"), nullable=False),
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
    op.create_index(op.f("ix_topic_vacancy_id"), "topic", ["vacancy_id"], unique=False)


def downgrade() -> None:
    """Откатывает ревизию."""
    op.drop_index(op.f("ix_topic_vacancy_id"), table_name="topic")
    op.drop_table("topic")
    op.drop_table("vacancy")
    for enum_name in ENUM_NAMES:
        sa.Enum(name=enum_name).drop(op.get_bind(), checkfirst=True)
