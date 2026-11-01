"""H3 spatial grid generation for the areas we crawl."""

import h3

try:
    from app.services.discovery.targets import CITY_BOUNDING_BOXES as _CITY_BOUNDING_BOXES
except ImportError:
    from targets import CITY_BOUNDING_BOXES as _CITY_BOUNDING_BOXES


def normalize_city_key(city_name: str) -> str:
    """Map 'Bengaluru Central' / 'bengaluru-central' to the 'bengaluru_central' key."""
    return "_".join(city_name.strip().lower().replace("-", " ").split())


def generate_city_cells(city_name: str, resolution: int = 9) -> list[str]:
    """Return H3 cell IDs covering `city_name`'s bounding box, nearest-to-centre first.

    Business density peaks around the centre, so scanning outward from it
    yields far more leads per cell than starting at an arbitrary corner.
    """
    key = normalize_city_key(city_name)
    if key not in _CITY_BOUNDING_BOXES:
        raise ValueError(f"No bounding box configured for city: {city_name!r}")

    bbox = _CITY_BOUNDING_BOXES[key]
    centre_lat = sum(lat for lat, _ in bbox) / len(bbox)
    centre_lng = sum(lng for _, lng in bbox) / len(bbox)
    centre_cell = h3.latlng_to_cell(centre_lat, centre_lng, resolution)

    cells = h3.polygon_to_cells(h3.LatLngPoly(bbox), resolution)
    # Tie-break on the ID so the order is deterministic across runs.
    return sorted(cells, key=lambda c: (h3.grid_distance(centre_cell, c), c))


def cell_to_coords(hex_id: str) -> tuple[float, float]:
    """Return the (lat, lng) centroid of an H3 cell."""
    return h3.cell_to_latlng(hex_id)


if __name__ == "__main__":
    cells = generate_city_cells("Bengaluru")
    print(f"Generated {len(cells)} cells for Bengaluru")
    print("Sample:", cells[0], "->", cell_to_coords(cells[0]))
