"""activity_events

Revision ID: a1b2c3d4e5f6
Revises: 64cd4beb4a5a

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '64cd4beb4a5a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('activity_events',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('client_event_id', sa.UUID(), nullable=False),
        sa.Column('timestamp', sa.DateTime(timezone=True), nullable=False),
        sa.Column('event_type', sa.String(length=50), nullable=False),
        sa.Column('app_name', sa.String(length=255), nullable=False),
        sa.Column('window_title', sa.String(length=2000), nullable=False),
        sa.Column('url', sa.String(length=2000), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'client_event_id', name='uq_activity_events_user_client_event'),
    )
    op.create_index('ix_activity_events_user_timestamp', 'activity_events', ['user_id', 'timestamp'])


def downgrade() -> None:
    op.drop_index('ix_activity_events_user_timestamp', table_name='activity_events')
    op.drop_table('activity_events')
