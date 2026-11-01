"""is_duplicate_lead against a throwaway SQLite copy of the leads table."""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.models import Lead
from app.services.discovery.gmaps_extractor import is_duplicate_lead


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    Lead.__table__.create(engine)
    with Session(engine) as session:
        session.add_all(
            [
                Lead(place_id="ChIJ_branch_1", business_name="Cult Fit", phone_number="9845012345",
                     city="Bengaluru", category="LAGGY_UX", origin_source_url=""),
                Lead(place_id=None, business_name="Old Gym", phone_number="9845099999",
                     city="Bengaluru", category="DIGITAL_GHOST", origin_source_url=""),
                Lead(place_id="ChIJ_switchboard", business_name="DesignCafe", phone_number="08068065000",
                     city="Bengaluru", category="LAGGY_UX", origin_source_url=""),
            ]
        )
        session.commit()
        yield session


def test_same_place_id_is_duplicate(db):
    assert is_duplicate_lead(db, "9000000001", "Renamed", "Bengaluru", "ChIJ_branch_1")


def test_chain_branch_with_own_place_and_number_is_new(db):
    assert not is_duplicate_lead(db, "9000000002", "Cult Fit", "Bengaluru", "ChIJ_branch_2")


def test_shared_phone_is_duplicate_even_for_another_branch(db):
    assert is_duplicate_lead(db, "+91 98450 12345", "Cult Fit", "Bengaluru", "ChIJ_branch_3")


def test_landline_matches_stored_trunk_zero(db):
    assert is_duplicate_lead(db, "080 6806 5000", "DesignCafe HSR", "Bengaluru", "ChIJ_other")


def test_name_and_city_still_dedupe_legacy_rows_without_place_id(db):
    assert is_duplicate_lead(db, "9000000003", "old gym", "Bengaluru", "ChIJ_new")


def test_name_and_city_used_when_incoming_has_no_place_id(db):
    assert is_duplicate_lead(db, "9000000004", "Cult Fit", "Bengaluru", None)
    assert not is_duplicate_lead(db, "9000000005", "Cult Fit", "Mysuru", None)
