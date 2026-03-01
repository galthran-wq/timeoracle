"""add_chats

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-03-01 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'e5f6a7b8c9d0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('chats',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('date', sa.Date(), nullable=True),
        sa.Column('trigger', sa.String(length=20), nullable=False),
        sa.Column('llm_model', sa.String(length=100), nullable=False),
        sa.Column('messages', postgresql.JSONB(astext_type=sa.Text()), server_default='[]', nullable=True),
        sa.Column('total_input_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('total_output_tokens', sa.Integer(), server_default='0', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    op.add_column('timeline_entries',
        sa.Column('chat_id', sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        'fk_timeline_entries_chat_id',
        'timeline_entries', 'chats',
        ['chat_id'], ['id'],
        ondelete='SET NULL',
    )


def downgrade() -> None:
    op.drop_constraint('fk_timeline_entries_chat_id', 'timeline_entries', type_='foreignkey')
    op.drop_column('timeline_entries', 'chat_id')
    op.drop_table('chats')
