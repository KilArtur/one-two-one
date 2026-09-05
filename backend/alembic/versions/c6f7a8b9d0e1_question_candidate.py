"""Scope adaptive questions to their candidate."""

import sqlalchemy as sa

from alembic import op

revision = "c6f7a8b9d0e1"
down_revision = "b5e6f7a8c9d0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Add ownership for personal and follow-up questions."""
    op.add_column("question", sa.Column("candidate_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "fk_question_candidate",
        "question",
        "candidate",
        ["candidate_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index("ix_question_candidate_id", "question", ["candidate_id"])


def downgrade() -> None:
    """Remove adaptive-question ownership."""
    op.drop_index("ix_question_candidate_id", table_name="question")
    op.drop_constraint("fk_question_candidate", "question", type_="foreignkey")
    op.drop_column("question", "candidate_id")
