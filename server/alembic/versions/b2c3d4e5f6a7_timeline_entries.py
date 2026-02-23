"""timeline_entries

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('timeline_entries',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('start_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('end_time', sa.DateTime(timezone=True), nullable=False),
        sa.Column('label', sa.String(length=255), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('category', sa.String(length=100), nullable=True),
        sa.Column('color', sa.String(length=7), nullable=True),
        sa.Column('source', sa.String(length=20), server_default='manual', nullable=False),
        sa.Column('source_summary', sa.Text(), nullable=True),
        sa.Column('confidence', sa.Float(), nullable=True),
        sa.Column('edited_by_user', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_timeline_entries_user_date', 'timeline_entries', ['user_id', 'date'])
    op.create_index('ix_timeline_entries_user_start_time', 'timeline_entries', ['user_id', 'start_time'])


def downgrade() -> None:
    op.drop_index('ix_timeline_entries_user_start_time', table_name='timeline_entries')
    op.drop_index('ix_timeline_entries_user_date', table_name='timeline_entries')
    op.drop_table('timeline_entries')
