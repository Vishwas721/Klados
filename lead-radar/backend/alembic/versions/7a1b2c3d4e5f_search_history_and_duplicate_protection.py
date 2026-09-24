"""search_history and duplicate protection

Revision ID: 7a1b2c3d4e5f
Revises: 0ac9f8adb27c
Create Date: 2026-09-24 13:55:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '7a1b2c3d4e5f'
down_revision: Union[str, Sequence[str], None] = '0ac9f8adb27c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Create search_history table
    op.create_table(
        'search_history',
        sa.Column('id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('niche', sa.String(length=255), nullable=False),
        sa.Column('city', sa.String(length=100), nullable=False),
        sa.Column('last_run_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('leads_count', sa.Integer(), server_default='0', nullable=False),
        sa.Column('status', sa.String(length=50), server_default='COMPLETED', nullable=False),
        sa.UniqueConstraint('niche', 'city', name='uq_search_history_niche_city'),
    )
    op.create_index(op.f('ix_search_history_niche'), 'search_history', ['niche'], unique=False)
    op.create_index(op.f('ix_search_history_city'), 'search_history', ['city'], unique=False)

    # 2. Add place_id and unique constraint to leads
    op.add_column('leads', sa.Column('place_id', sa.String(length=255), nullable=True))
    op.create_index(op.f('ix_leads_place_id'), 'leads', ['place_id'], unique=True)
    op.create_unique_constraint('uq_leads_phone_business', 'leads', ['phone_number', 'business_name'])


def downgrade() -> None:
    op.drop_constraint('uq_leads_phone_business', 'leads', type_='unique')
    op.drop_index(op.f('ix_leads_place_id'), table_name='leads')
    op.drop_column('leads', 'place_id')

    op.drop_index(op.f('ix_search_history_city'), table_name='search_history')
    op.drop_index(op.f('ix_search_history_niche'), table_name='search_history')
    op.drop_table('search_history')
