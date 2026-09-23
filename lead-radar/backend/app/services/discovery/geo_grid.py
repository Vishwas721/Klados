"""H3 spatial grid generation for the areas we crawl."""

import h3

try:
    from app.services.discovery.targets import CITY_BOUNDING_BOXES as _CITY_BOUNDING_BOXES
except ImportError:
    from targets import CITY_BOUNDING_BOXES as _CITY_BOUNDING_BOXES



def generate_city_cells(city_name: str, resolution: int = 9) -> list[str]:
    """Return H3 cell IDs covering the known bounding box for `city_name`."""
    key = city_name.strip().lower()
    if key not in _CITY_BOUNDING_BOXES:
        raise ValueError(f"No bounding box configured for city: {city_name!r}")

    polygon = h3.LatLngPoly(_CITY_BOUNDING_BOXES[key])
    return list(h3.polygon_to_cells(polygon, resolution))


def cell_to_coords(hex_id: str) -> tuple[float, float]:
    """Return the (lat, lng) centroid of an H3 cell."""
    return h3.cell_to_latlng(hex_id)


if __name__ == "__main__":
    cells = generate_city_cells("Bengaluru")
    print(f"Generated {len(cells)} cells for Bengaluru")
    print("Sample:", cells[0], "->", cell_to_coords(cells[0]))
