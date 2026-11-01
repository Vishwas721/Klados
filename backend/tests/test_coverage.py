import h3
import pytest

from app.services.discovery.coverage import (
    SEEN_CELLS_TTL_S,
    mark_seen,
    seen_cells_key,
    unmark_seen,
    unseen_cells,
)
from app.services.discovery.geo_grid import generate_city_cells, normalize_city_key


@pytest.mark.parametrize("name", ["Bengaluru Central", "bengaluru-central", "  BENGALURU_central "])
def test_normalize_city_key(name):
    assert normalize_city_key(name) == "bengaluru_central"


def test_cells_ordered_from_centre_outward():
    cells = generate_city_cells("Udupi Manipal")
    distances = [h3.grid_distance(cells[0], c) for c in cells[:50]]
    assert distances[0] == 0
    assert distances == sorted(distances)


def test_cells_are_deterministic():
    assert generate_city_cells("Mysuru") == generate_city_cells("mysuru")


def test_unknown_city_raises():
    with pytest.raises(ValueError):
        generate_city_cells("Delhi")


def test_successive_scans_cover_new_cells(fake_redis):
    first = unseen_cells(fake_redis, "Mysuru", "Gyms")[:6]
    mark_seen(fake_redis, "Mysuru", "Gyms", first)
    second = unseen_cells(fake_redis, "Mysuru", "Gyms")[:6]

    assert not set(first) & set(second)
    assert fake_redis.ttls[seen_cells_key("Mysuru", "Gyms")] == SEEN_CELLS_TTL_S


def test_unmark_releases_cell(fake_redis):
    cell = generate_city_cells("Mysuru")[0]
    mark_seen(fake_redis, "Mysuru", "Gyms", [cell])
    unmark_seen(fake_redis, "Mysuru", "Gyms", cell)
    assert unseen_cells(fake_redis, "Mysuru", "Gyms")[0] == cell


def test_key_is_case_insensitive():
    assert seen_cells_key(" Mysuru ", "GYMS") == seen_cells_key("mysuru", "gyms")
