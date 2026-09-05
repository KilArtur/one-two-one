"""Связь ответа с кандидатом и манифест чанковой загрузки."""

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision = "e2b3c4d5e6f7"
down_revision = "d1a2b3c4e5f6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("answer", sa.Column("candidate_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_answer_candidate", "answer", "candidate", ["candidate_id"], ["id"], ondelete="CASCADE"
    )
    op.create_index("ix_answer_candidate_id", "answer", ["candidate_id"])
    op.create_unique_constraint(
        "uq_answer_candidate_question", "answer", ["candidate_id", "question_id"]
    )
    op.create_table(
        "answer_upload",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "candidate_id",
            sa.Uuid(),
            sa.ForeignKey("candidate.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "question_id",
            sa.Uuid(),
            sa.ForeignKey("question.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("manifest", postgresql.JSONB(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.UniqueConstraint("candidate_id", "question_id"),
    )


def downgrade() -> None:
    op.drop_table("answer_upload")
    op.drop_constraint("uq_answer_candidate_question", "answer", type_="unique")
    op.drop_index("ix_answer_candidate_id", table_name="answer")
    op.drop_constraint("fk_answer_candidate", "answer", type_="foreignkey")
    op.drop_column("answer", "candidate_id")
