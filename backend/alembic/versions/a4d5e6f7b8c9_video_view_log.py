"""Аудит просмотров видео."""

import sqlalchemy as sa

from alembic import op

revision = "a4d5e6f7b8c9"
down_revision = "f3c4d5e6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "video_view_log",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "answer_id", sa.Uuid(), sa.ForeignKey("answer.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("viewer", sa.String(255), nullable=False),
        sa.Column("role", sa.String(40), nullable=False),
        sa.Column("position_sec", sa.Float(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
    )
    op.create_index("ix_video_view_log_answer_id", "video_view_log", ["answer_id"])


def downgrade() -> None:
    op.drop_table("video_view_log")
