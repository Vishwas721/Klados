"""H3 spatial grid generation for the areas we crawl."""

import h3

# Rough bounding box over central Bengaluru, covering Koramangala, Indiranagar,
# HSR Layout and MG Road. (lat, lng) pairs.
_CITY_BOUNDING_BOXES: dict[str, list[tuple[float, float]]] = {
    "bengaluru": [
        (12.99, 77.59),  # NW, near MG Road / Indiranagar
        (12.99, 77.66),  # NE, past Indiranagar
        (12.90, 77.66),  # SE, past HSR Layout
        (12.90, 77.59),  # SW, near Koramangala
    ],
}


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
