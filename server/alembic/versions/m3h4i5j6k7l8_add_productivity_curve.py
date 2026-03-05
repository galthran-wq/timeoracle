"""add productivity curve

Revision ID: m3h4i5j6k7l8
Revises: l2g3h4i5j6k7
Create Date: 2026-03-04
"""
from typing import Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision: str = "m3h4i5j6k7l8"
down_revision: Union[str, None] = "l2g3h4i5j6k7"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "productivity_points",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("interval_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("focus_score", sa.Float(), nullable=True),
        sa.Column("depth", sa.String(20), nullable=True),
        sa.Column("productivity_score", sa.Float(), nullable=True),
        sa.Column("category", sa.String(100), nullable=True),
        sa.Column("color", sa.String(7), nullable=True),
        sa.Column("is_work", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("timeline_entry_id", UUID(as_uuid=True), sa.ForeignKey("timeline_entries.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "interval_start", name="uq_productivity_points_user_interval"),
    )
    op.create_index("ix_productivity_points_user_date", "productivity_points", ["user_id", "date"])

    op.add_column("day_summaries", sa.Column("productivity_score", sa.Float(), nullable=True))
    op.add_column("day_summaries", sa.Column("work_minutes", sa.Float(), server_default="0", nullable=False))

    op.drop_column("timeline_entries", "focus_score")
    op.drop_column("timeline_entries", "depth")


def downgrade() -> None:
    op.add_column("timeline_entries", sa.Column("depth", sa.String(20), nullable=True))
    op.add_column("timeline_entries", sa.Column("focus_score", sa.Float(), nullable=True))

    op.drop_column("day_summaries", "work_minutes")
    op.drop_column("day_summaries", "productivity_score")

    op.drop_index("ix_productivity_points_user_date", table_name="productivity_points")
    op.drop_table("productivity_points")
