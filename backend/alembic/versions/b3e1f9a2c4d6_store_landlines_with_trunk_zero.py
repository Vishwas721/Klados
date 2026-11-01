"""store landlines with their trunk 0

Revision ID: b3e1f9a2c4d6
Revises: 67a56d45c741
Create Date: 2026-11-01 12:00:00.000000

The old normalizer stripped the trunk 0 from any 11-digit number whose
second digit was 6-9, so Bengaluru (080), Ahmedabad (079) and other
Karnataka landlines were stored as bare 10 digits and got WhatsApp links.
Re-derive each 10-digit number's type with libphonenumber and prefix the
landlines with 0, which is how the extractor now stores them.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.services.discovery.phones import normalize_indian_phone


# revision identifiers, used by Alembic.
revision: str = 'b3e1f9a2c4d6'
down_revision: Union[str, Sequence[str], None] = '67a56d45c741'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(
        sa.text("SELECT id, phone_number FROM leads WHERE phone_number ~ '^[1-9][0-9]{9}$'")
    ).all()
    update = sa.text("UPDATE leads SET phone_number = :new WHERE id = :id")
    for lead_id, phone in rows:
        normalized = normalize_indian_phone(phone)
        if normalized and normalized != phone and normalized.startswith("0"):
            conn.execute(update, {"id": lead_id, "new": normalized})


def downgrade() -> None:
    # The old format kept the 0 only when the STD code didn't start with 6-9
    op.execute(
        "UPDATE leads SET phone_number = substr(phone_number, 2) "
        "WHERE phone_number ~ '^0[6-9][0-9]{9}$'"
    )
