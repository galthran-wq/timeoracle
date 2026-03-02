"""add day_summaries

Revision ID: j0e1f2g3h4i5
Revises: i9d0e1f2g3h4
Create Date: 2026-03-02
"""
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "j0e1f2g3h4i5"
down_revision: Union[str, None] = "i9d0e1f2g3h4"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "day_summaries",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("total_active_minutes", sa.Float(), server_default="0", nullable=False),
        sa.Column("productive_minutes", sa.Float(), server_default="0", nullable=False),
        sa.Column("neutral_minutes", sa.Float(), server_default="0", nullable=False),
        sa.Column("distraction_minutes", sa.Float(), server_default="0", nullable=False),
        sa.Column("uncategorized_minutes", sa.Float(), server_default="0", nullable=False),
        sa.Column("focus_score", sa.Float(), nullable=True),
        sa.Column("distraction_score", sa.Float(), nullable=True),
        sa.Column("longest_focus_minutes", sa.Float(), server_default="0", nullable=False),
        sa.Column("context_switches", sa.Integer(), server_default="0", nullable=False),
        sa.Column("session_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("top_app", sa.String(255), nullable=True),
        sa.Column("top_category", sa.String(100), nullable=True),
        sa.Column("category_breakdown", JSONB(), nullable=True),
        sa.Column("app_breakdown", JSONB(), nullable=True),
        sa.Column("narrative", sa.Text(), nullable=True),
        sa.Column("is_partial", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "date", name="uq_day_summaries_user_date"),
    )
    op.create_index("ix_day_summaries_user_date", "day_summaries", ["user_id", "date"])


def downgrade() -> None:
    op.drop_index("ix_day_summaries_user_date", table_name="day_summaries")
    op.drop_table("day_summaries")
