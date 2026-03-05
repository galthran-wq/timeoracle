"""drop category type metrics

Revision ID: l2g3h4i5j6k7
Revises: k1f2g3h4i5j6
Create Date: 2026-03-04
"""
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "l2g3h4i5j6k7"
down_revision: Union[str, None] = "k1f2g3h4i5j6"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.drop_column("day_summaries", "productive_minutes")
    op.drop_column("day_summaries", "neutral_minutes")
    op.drop_column("day_summaries", "distraction_minutes")
    op.drop_column("day_summaries", "uncategorized_minutes")
    op.drop_column("day_summaries", "focus_score")
    op.drop_column("day_summaries", "distraction_score")


def downgrade() -> None:
    op.add_column("day_summaries", sa.Column("distraction_score", sa.Float(), nullable=True))
    op.add_column("day_summaries", sa.Column("focus_score", sa.Float(), nullable=True))
    op.add_column("day_summaries", sa.Column("uncategorized_minutes", sa.Float(), server_default="0", nullable=False))
    op.add_column("day_summaries", sa.Column("distraction_minutes", sa.Float(), server_default="0", nullable=False))
    op.add_column("day_summaries", sa.Column("neutral_minutes", sa.Float(), server_default="0", nullable=False))
    op.add_column("day_summaries", sa.Column("productive_minutes", sa.Float(), server_default="0", nullable=False))
