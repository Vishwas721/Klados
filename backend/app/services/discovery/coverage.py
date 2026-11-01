"""Per-(city, niche) record of which H3 cells have already been scanned.

Shared by the API (picking a scan's starting cells) and the worker (spatial
expansion), so both agree on the Redis key and every write refreshes its TTL.
"""

from redis import Redis

from app.services.discovery.geo_grid import generate_city_cells

# Long enough to work through a city over many daily runs, short enough
# that a fully covered city is eventually rescanned for new businesses.
SEEN_CELLS_TTL_S = 30 * 24 * 3600


def seen_cells_key(city: str, niche: str) -> str:
    return f"seen_cells:{city.strip().lower()}:{niche.strip().lower()}"


def mark_seen(r: Redis, city: str, niche: str, cells: list[str]) -> None:
    if not cells:
        return
    key = seen_cells_key(city, niche)
    r.sadd(key, *cells)
    r.expire(key, SEEN_CELLS_TTL_S)


def unmark_seen(r: Redis, city: str, niche: str, cell: str) -> None:
    """Release a cell that was claimed but never actually scraped."""
    r.srem(seen_cells_key(city, niche), cell)


def unseen_cells(r: Redis, city: str, niche: str) -> list[str]:
    """City cells not yet scanned for this niche, nearest-to-centre first.

    Raises ValueError for a city without a configured bounding box.
    """
    seen = {
        c.decode() if isinstance(c, bytes) else c
        for c in r.smembers(seen_cells_key(city, niche))
    }
    return [c for c in generate_city_cells(city) if c not in seen]
