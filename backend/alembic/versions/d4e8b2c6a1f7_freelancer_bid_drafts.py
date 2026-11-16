"""rewrite Freelancer.com reply drafts as bid proposals

Revision ID: d4e8b2c6a1f7
Revises: c7d2a8f1e3b9
Create Date: 2026-11-16 18:00:00.000000

Freelancer.com posts saved before bid drafts existed carry a short chat-style
first message. Regenerate the template draft (with a suggested price and
timeline) for the ones still in the inbox or shortlist. Drafts Ollama wrote
are replaced too: they were written without a price.
"""
from types import SimpleNamespace
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.services.intent.bidding import bid_for_post
from app.services.intent.writer import draft_reply


# revision identifiers, used by Alembic.
revision: str = 'd4e8b2c6a1f7'
down_revision: Union[str, Sequence[str], None] = 'c7d2a8f1e3b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    rows = conn.execute(sa.text(
        "SELECT id, source, title, author, fit, budget_min, budget_max, currency, budget_usd, signals "
        "FROM intent_posts WHERE source = 'freelancer' AND status IN ('NEW', 'SAVED')"
    )).mappings().all()
    for row in rows:
        post = SimpleNamespace(**row)
        draft = draft_reply(post.source, post.fit, post.title, post.author, bid_for_post(post))
        conn.execute(sa.text("UPDATE intent_posts SET reply_draft = :d WHERE id = :id"), {"d": draft, "id": row["id"]})


def downgrade() -> None:
    pass  # drafts are regenerable text; nothing to restore
