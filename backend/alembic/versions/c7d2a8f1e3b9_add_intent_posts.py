"""add intent_posts for the request radar

Revision ID: c7d2a8f1e3b9
Revises: b3e1f9a2c4d6
Create Date: 2026-11-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c7d2a8f1e3b9'
down_revision: Union[str, Sequence[str], None] = 'b3e1f9a2c4d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'intent_posts',
        sa.Column('id', sa.UUID(), nullable=False),
        sa.Column('source', sa.String(length=20), nullable=False),
        sa.Column('external_id', sa.String(length=255), nullable=False),
        sa.Column('url', sa.Text(), nullable=False),
        sa.Column('title', sa.String(length=500), nullable=False),
        sa.Column('body', sa.Text(), nullable=False, server_default=''),
        sa.Column('author', sa.String(length=255), nullable=True),
        sa.Column('channel', sa.String(length=255), nullable=True),
        sa.Column('posted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('budget_min', sa.Float(), nullable=True),
        sa.Column('budget_max', sa.Float(), nullable=True),
        sa.Column('currency', sa.String(length=10), nullable=True),
        sa.Column('budget_usd', sa.Float(), nullable=True),
        sa.Column('bid_count', sa.Integer(), nullable=True),
        sa.Column('fit', sa.String(length=30), nullable=False),
        sa.Column('score', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('signals', sa.JSON(), nullable=False, server_default='[]'),
        sa.Column('is_local', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('summary', sa.Text(), nullable=True),
        sa.Column('reply_draft', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='NEW'),
        sa.Column('alerted', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('source', 'external_id', name='uq_intent_posts_source_external'),
    )
    for column in ('source', 'posted_at', 'fit', 'score', 'status', 'created_at'):
        op.create_index(f'ix_intent_posts_{column}', 'intent_posts', [column])


def downgrade() -> None:
    op.drop_table('intent_posts')
