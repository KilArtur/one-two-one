"""staff_user and candidate.full_name

Регистрация внутренних пользователей и отображаемое имя кандидата.

Revision ID: a1b2c3d4e5f6
Revises: f9a0b1c2d3e4
Create Date: 2026-09-06 18:30:00.000000
"""

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "a1b2c3d4e5f6"
down_revision: str | Sequence[str] | None = "f9a0b1c2d3e4"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Применяет ревизию."""
    op.execute(
        "DO $$ BEGIN "
        "CREATE TYPE app_role AS ENUM "
        "('recruiter', 'technical_specialist', 'hiring_manager'); "
        "EXCEPTION WHEN duplicate_object THEN NULL; END $$"
    )
    op.create_table(
        "staff_user",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("username", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role",
            # postgresql.ENUM: sa.Enum(create_type=False) всё равно эмитит CREATE TYPE
            postgresql.ENUM(
                "recruiter",
                "technical_specialist",
                "hiring_manager",
                name="app_role",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("username"),
    )
    op.create_index("ix_staff_user_username", "staff_user", ["username"])
    op.add_column("candidate", sa.Column("full_name", sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Откатывает ревизию."""
    op.drop_column("candidate", "full_name")
    op.drop_index("ix_staff_user_username", table_name="staff_user")
    op.drop_table("staff_user")
    op.execute("DROP TYPE IF EXISTS app_role")
