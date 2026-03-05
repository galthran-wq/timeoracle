"""add focus and depth metrics

Revision ID: k1f2g3h4i5j6
Revises: j0e1f2g3h4i5
Create Date: 2026-03-04
"""
from typing import Union

from alembic import op
import sqlalchemy as sa

revision: str = "k1f2g3h4i5j6"
down_revision: Union[str, None] = "j0e1f2g3h4i5"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("timeline_entries", sa.Column("focus_score", sa.Float(), nullable=True))
    op.add_column("timeline_entries", sa.Column("depth", sa.String(20), nullable=True))

    op.add_column("day_summaries", sa.Column("deep_work_minutes", sa.Float(), server_default="0", nullable=False))
    op.add_column("day_summaries", sa.Column("shallow_work_minutes", sa.Float(), server_default="0", nullable=False))
    op.add_column("day_summaries", sa.Column("reactive_minutes", sa.Float(), server_default="0", nullable=False))
    op.add_column("day_summaries", sa.Column("avg_focus_score", sa.Float(), nullable=True))
    op.add_column("day_summaries", sa.Column("fragmentation_index", sa.Float(), nullable=True))
    op.add_column("day_summaries", sa.Column("switches_per_hour", sa.Float(), nullable=True))
    op.add_column("day_summaries", sa.Column("focus_sessions_25min", sa.Integer(), server_default="0", nullable=False))
    op.add_column("day_summaries", sa.Column("focus_sessions_90min", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    op.drop_column("day_summaries", "focus_sessions_90min")
    op.drop_column("day_summaries", "focus_sessions_25min")
    op.drop_column("day_summaries", "switches_per_hour")
    op.drop_column("day_summaries", "fragmentation_index")
    op.drop_column("day_summaries", "avg_focus_score")
    op.drop_column("day_summaries", "reactive_minutes")
    op.drop_column("day_summaries", "shallow_work_minutes")
    op.drop_column("day_summaries", "deep_work_minutes")

    op.drop_column("timeline_entries", "depth")
    op.drop_column("timeline_entries", "focus_score")
