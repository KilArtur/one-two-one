"""Отзываемые ссылки на результат."""

import sqlalchemy as sa

from alembic import op

revision = "b5e6f7a8c9d0"
down_revision = "a4d5e6f7b8c9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "result_link",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.Uuid(),
            sa.ForeignKey("candidate.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("created_by", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_result_link_candidate_id", "result_link", ["candidate_id"])


def downgrade() -> None:
    op.drop_table("result_link")
