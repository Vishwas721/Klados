"""Find SearchHistory / CampaignTracker rows by canonical (city, niche).

Rows keep the niche and city exactly as first typed, so matching happens on
normalized keys in Python. Both tables hold one row per target, small
enough to scan.
"""

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CampaignTracker, SearchHistory
from app.services.discovery.coverage import SEEN_CELLS_TTL_S
from app.services.discovery.geo_grid import normalize_city_key
from app.services.discovery.targets import niche_key


def target_key(city: str, niche: str) -> tuple[str, str]:
    return normalize_city_key(city), niche_key(niche)


def _latest(rows, key: tuple[str, str], timestamp_attr: str):
    matches = [r for r in rows if target_key(r.city, r.niche) == key]
    epoch = datetime.min.replace(tzinfo=timezone.utc)
    return max(matches, key=lambda r: getattr(r, timestamp_attr) or epoch, default=None)


def find_search_history(db: Session, city: str, niche: str) -> SearchHistory | None:
    rows = db.execute(select(SearchHistory)).scalars().all()
    return _latest(rows, target_key(city, niche), "last_run_at")


def find_campaign(db: Session, city: str, niche: str) -> CampaignTracker | None:
    rows = db.execute(select(CampaignTracker)).scalars().all()
    return _latest(rows, target_key(city, niche), "last_scraped_at")


def clear_stale_exhaustion(db: Session) -> None:
    """Un-exhaust targets whose coverage record has expired.

    Exhaustion means "every cell seen"; once the seen-cell set lapses after
    SEEN_CELLS_TTL_S the city is due a fresh pass for new businesses.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=SEEN_CELLS_TTL_S)
    stale = db.execute(
        select(CampaignTracker).where(
            CampaignTracker.is_exhausted.is_(True),
            CampaignTracker.last_scraped_at < cutoff,
        )
    ).scalars().all()
    for tracker in stale:
        tracker.is_exhausted = False
    if stale:
        db.commit()
