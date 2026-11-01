from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.lookups import clear_stale_exhaustion, find_campaign, find_search_history
from app.db.models import CampaignTracker, SearchHistory
from app.services.discovery.coverage import seen_cells_key
from app.services.discovery.targets import niche_key


@pytest.mark.parametrize(
    "a, b",
    [
        ("Gyms", "gym"),
        ("Pet Care & Veterinary", "pet care and veterinary"),
        ("Dental Clinics", "dental clinic"),
        ("  Yoga   Studios ", "yoga studio"),
        ("Coaching Classes", "coaching class"),
        ("Car Accessories", "car accessory"),
        ("Fitness", "fitness"),
    ],
)
def test_niche_key_equivalents(a, b):
    assert niche_key(a) == niche_key(b)


def test_niche_key_keeps_distinct_niches_apart():
    assert niche_key("gym") != niche_key("yoga")


def test_coverage_key_shared_across_spellings():
    assert seen_cells_key("Bengaluru Central", "Gyms") == seen_cells_key("bengaluru-central", "gym")


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    SearchHistory.__table__.create(engine)
    CampaignTracker.__table__.create(engine)
    with Session(engine) as session:
        yield session


def test_find_search_history_matches_canonical_target(db):
    now = datetime.now(timezone.utc)
    db.add_all(
        [
            SearchHistory(niche="Gyms", city="Bengaluru", last_run_at=now - timedelta(days=3)),
            SearchHistory(niche="gym", city="bengaluru", last_run_at=now),
            SearchHistory(niche="Gyms", city="Mysuru", last_run_at=now),
        ]
    )
    db.commit()

    found = find_search_history(db, "BENGALURU", "gyms")
    assert (found.niche, found.city) == ("gym", "bengaluru")  # most recent of the two
    assert find_search_history(db, "Pune", "Gyms") is None


def test_stale_exhaustion_is_cleared(db):
    now = datetime.now(timezone.utc)
    db.add_all(
        [
            CampaignTracker(city="Mysuru", niche="Gyms", is_exhausted=True, last_scraped_at=now - timedelta(days=45)),
            CampaignTracker(city="Udupi Manipal", niche="Gyms", is_exhausted=True, last_scraped_at=now),
        ]
    )
    db.commit()

    clear_stale_exhaustion(db)

    assert find_campaign(db, "mysuru", "gym").is_exhausted is False
    assert find_campaign(db, "udupi-manipal", "gyms").is_exhausted is True
