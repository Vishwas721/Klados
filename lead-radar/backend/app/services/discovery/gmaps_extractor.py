"""Direct extraction from Google's undocumented `tbm=map` search endpoint."""

import json
import re
from urllib.parse import quote, urlparse

import httpx

from app.services.discovery.geo_grid import cell_to_coords, generate_city_cells

SEARCH_URL = "https://www.google.com/search"
XSSI_PREFIX = ")]}'"

PHONE_REGEX = re.compile(r"(?:\+91[\-\s]?)?[6-9]\d{9}")
_PLACE_ID_REGEX = re.compile(r"^0x[0-9a-fA-F]+:0x[0-9a-fA-F]+$|^[a-zA-Z0-9_-]{20,}$")

_EXCLUDED_WEBSITE_HOSTS = (
    "google.com",
    "googleusercontent.com",
    "gstatic.com",
    "schema.org",
    "justdial.com",
    "sulekha.com",
    "indiamart.com",
    "yellowpages.in",
)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
    "Accept-Language": "en-IN,en;q=0.9",
}


def _strip_xssi_prefix(text: str) -> str:
    text = text.strip()
    return text[len(XSSI_PREFIX):] if text.startswith(XSSI_PREFIX) else text


def _build_request_url(query: str, lat: float, lng: float, limit: int) -> str:
    pb = f"!1m2!1s{lat}!2s{lng}!7i{limit}"
    return f"{SEARCH_URL}?tbm=map&q={quote(query)}&pb={pb}"


def _is_valid_website(url: str) -> bool:
    if not isinstance(url, str) or not url.startswith("http"):
        return False
    host = urlparse(url).netloc.lower()
    if not host:
        return False
    return not any(host == d or host.endswith("." + d) for d in _EXCLUDED_WEBSITE_HOSTS)


def _flatten_strings(node, out: list) -> None:
    if isinstance(node, str):
        out.append(node)
    elif isinstance(node, list):
        for item in node:
            _flatten_strings(item, out)


def _extract_place_entries(payload) -> list:
    """Locate the list of per-business result arrays inside the payload.

    Google reshuffles this undocumented structure's array indices without
    notice, so instead of hard-coding positions we scan the tree for the
    largest list-of-lists group, which is reliably the results list.
    """
    candidates = []

    def _walk(node):
        if isinstance(node, list):
            if node and all(isinstance(item, list) for item in node):
                candidates.append(node)
            for item in node:
                _walk(item)

    _walk(payload)
    candidates.sort(key=len, reverse=True)
    return candidates[0] if candidates else []


def _extract_coords(entry, fallback: tuple) -> tuple:
    numbers = []

    def _walk(node):
        if isinstance(node, (int, float)) and not isinstance(node, bool):
            numbers.append(float(node))
        elif isinstance(node, list):
            for item in node:
                _walk(item)

    _walk(entry)

    for i in range(len(numbers) - 1):
        lat, lng = numbers[i], numbers[i + 1]
        if 6.0 <= lat <= 37.0 and 68.0 <= lng <= 97.0:
            return lat, lng
    return fallback


def _extract_business_name(strings: list) -> str | None:
    candidates = []
    for s in strings:
        candidate = s.strip()
        if not candidate or candidate.startswith("http"):
            continue
        if PHONE_REGEX.fullmatch(candidate) or candidate.isdigit():
            continue
        if _PLACE_ID_REGEX.match(candidate):
            continue
        if 2 <= len(candidate) <= 120:
            candidates.append(candidate)

    if not candidates:
        return None

    # Real business names almost always contain a space; opaque tokens
    # (feature IDs, category slugs) usually don't.
    with_space = [c for c in candidates if " " in c]
    return with_space[0] if with_space else candidates[0]


def _parse_entry(entry, query_url: str, fallback_coords: tuple) -> dict | None:
    strings: list = []
    _flatten_strings(entry, strings)
    if not strings:
        return None

    business_name = _extract_business_name(strings)
    if not business_name:
        return None

    phone_match = PHONE_REGEX.search(" ".join(strings))
    phone_number = phone_match.group(0) if phone_match else None

    website_url = next((s for s in strings if _is_valid_website(s)), None)

    latitude, longitude = _extract_coords(entry, fallback_coords)

    return {
        "business_name": business_name,
        "phone_number": phone_number,
        "website_url": website_url,
        "origin_source_url": query_url,
        "latitude": latitude,
        "longitude": longitude,
        "category": "DIGITAL_GHOST" if website_url is None else None,
    }


def extract_places(query: str, lat: float, lng: float, limit: int = 20) -> list:
    url = _build_request_url(query, lat, lng, limit)

    with httpx.Client(headers=_HEADERS, timeout=15.0, follow_redirects=True) as client:
        response = client.get(url)
        response.raise_for_status()

    cleaned = _strip_xssi_prefix(response.text)

    try:
        payload = json.loads(cleaned)
    except json.JSONDecodeError:
        return []

    results = []
    seen_names = set()
    for entry in _extract_place_entries(payload):
        place = _parse_entry(entry, url, (lat, lng))
        if place is None or place["business_name"] in seen_names:
            continue
        seen_names.add(place["business_name"])
        results.append(place)
        if len(results) >= limit:
            break

    return results


if __name__ == "__main__":
    cell = generate_city_cells("Bengaluru")[0]
    cell_lat, cell_lng = cell_to_coords(cell)

    places = extract_places("dental clinic", cell_lat, cell_lng, limit=20)
    print(json.dumps(places, indent=2))
