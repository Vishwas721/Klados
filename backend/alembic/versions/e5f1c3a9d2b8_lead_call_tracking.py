"""call desk: track phone outcomes on leads

Revision ID: e5f1c3a9d2b8
Revises: d4e8b2c6a1f7
Create Date: 2026-11-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5f1c3a9d2b8'
down_revision: Union[str, Sequence[str], None] = 'd4e8b2c6a1f7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('leads', sa.Column('call_outcome', sa.String(length=20), nullable=True))
    op.add_column('leads', sa.Column('call_attempts', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('leads', sa.Column('last_called_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('leads', sa.Column('next_call_at', sa.DateTime(timezone=True), nullable=True))
    op.add_column('leads', sa.Column('call_notes', sa.Text(), nullable=True))
    op.create_index('ix_leads_call_outcome', 'leads', ['call_outcome'])


def downgrade() -> None:
    op.drop_index('ix_leads_call_outcome', table_name='leads')
    for column in ('call_notes', 'next_call_at', 'last_called_at', 'call_attempts', 'call_outcome'):
        op.drop_column('leads', column)
