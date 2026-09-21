"""Google Maps business discovery via a Camoufox-driven headless browser.

The Maps search sidebar is a single-page app: results are lazy-loaded into
a `div[role="feed"]` as the user scrolls, built from JS-side session tokens
that a plain HTTP GET can't reproduce (confirmed by capturing the page's own
XHR traffic - the `tbm=map` request it issues is signed with a short-lived
session id minted by the page's JS). So instead of hitting that endpoint
directly, we drive an actual (stealth) browser and read the rendered DOM.
"""

import asyncio
import re
from urllib.parse import quote, urlparse

from camoufox.async_api import AsyncCamoufox

from app.services.discovery.geo_grid import cell_to_coords, generate_city_cells

MAPS_SEARCH_URL = "https://www.google.com/maps/search/{query}/@{lat},{lng},15z"

FEED_SELECTOR = 'div[role="feed"]'
CARD_SELECTOR = 'div[role="article"]'
NAME_LINK_SELECTOR = "a.hfpxzc"
WEBSITE_LINK_SELECTOR = 'a[data-value="Website"]'

PHONE_REGEX = re.compile(r"(?:\+91[\-\s]?)?[6-9]\d{9}")
_RAW_PHONE_CANDIDATE = re.compile(r"(\+?\d[\d\s\-]{7,14}\d)")
_COORDS_IN_HREF = re.compile(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)")

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


def _is_valid_website(url: str | None) -> bool:
    if not url or not url.startswith("http"):
        return False
    host = urlparse(url).netloc.lower()
    if not host:
        return False
    return not any(host == d or host.endswith("." + d) for d in _EXCLUDED_WEBSITE_HOSTS)


def _normalize_phone(raw: str) -> str | None:
    digits = re.sub(r"[^\d+]", "", raw)
    if digits.startswith("+91"):
        digits = digits[3:]
    elif digits.startswith("91") and len(digits) == 12:
        digits = digits[2:]
    elif digits.startswith("0") and len(digits) == 11:
        digits = digits[1:]
    return digits if PHONE_REGEX.fullmatch(digits) else None


def _extract_phone(card_text: str) -> str | None:
    for raw in _RAW_PHONE_CANDIDATE.findall(card_text):
        normalized = _normalize_phone(raw)
        if normalized:
            return normalized
    return None


def _extract_coords(href: str | None, fallback: tuple) -> tuple:
    match = _COORDS_IN_HREF.search(href or "")
    if not match:
        return fallback
    return float(match.group(1)), float(match.group(2))


async def _scroll_feed(page, target_count: int, max_rounds: int = 12, pause_ms: int = 1200) -> None:
    feed = page.locator(FEED_SELECTOR)
    await feed.hover()

    previous_count = -1
    stalled_rounds = 0
    for _ in range(max_rounds):
        current_count = await page.locator(CARD_SELECTOR).count()
        if current_count >= target_count:
            return
        if current_count == previous_count:
            stalled_rounds += 1
            if stalled_rounds >= 2:
                return  # end of results reached
        else:
            stalled_rounds = 0
        previous_count = current_count

        await page.mouse.wheel(0, 1200)
        await page.keyboard.press("PageDown")
        await page.wait_for_timeout(pause_ms)


async def _extract_from_feed(page, query_url: str, fallback_coords: tuple, limit: int) -> list:
    cards = page.locator(CARD_SELECTOR)
    count = await cards.count()

    results = []
    seen_names = set()
    for i in range(count):
        card = cards.nth(i)

        name_link = card.locator(NAME_LINK_SELECTOR).first
        if await name_link.count() == 0:
            continue

        business_name = (await name_link.get_attribute("aria-label") or "").strip()
        if not business_name or business_name in seen_names:
            continue

        place_href = await name_link.get_attribute("href")
        latitude, longitude = _extract_coords(place_href, fallback_coords)

        website_link = card.locator(WEBSITE_LINK_SELECTOR).first
        website_url = None
        if await website_link.count() > 0:
            href = await website_link.get_attribute("href")
            if _is_valid_website(href):
                website_url = href

        card_text = await card.inner_text()
        phone_number = _extract_phone(card_text)

        seen_names.add(business_name)
        results.append(
            {
                "business_name": business_name,
                "phone_number": phone_number,
                "website_url": website_url,
                "origin_source_url": query_url,
                "latitude": latitude,
                "longitude": longitude,
                "category": "DIGITAL_GHOST" if website_url is None else None,
            }
        )
        if len(results) >= limit:
            break

    return results


async def _extract_places_async(query: str, lat: float, lng: float, limit: int) -> list:
    url = MAPS_SEARCH_URL.format(query=quote(query), lat=lat, lng=lng)

    camoufox = AsyncCamoufox(headless=True, geoip=True, locale="en-IN")
    browser = None
    try:
        browser = await camoufox.__aenter__()
        page = await browser.new_page()
        await page.goto(url, wait_until="networkidle", timeout=45000)

        try:
            await page.wait_for_selector(FEED_SELECTOR, timeout=15000)
        except Exception:
            return []

        await _scroll_feed(page, target_count=limit)
        return await _extract_from_feed(page, url, (lat, lng), limit)
    finally:
        await camoufox.__aexit__(None, None, None)


def extract_places(query: str, lat: float, lng: float, limit: int = 20) -> list:
    """Search Google Maps around (lat, lng) and return parsed business leads."""
    return asyncio.run(_extract_places_async(query, lat, lng, limit))


if __name__ == "__main__":
    import json

    cell = generate_city_cells("Bengaluru")[0]
    cell_lat, cell_lng = cell_to_coords(cell)

    places = extract_places("dental clinic", cell_lat, cell_lng, limit=20)
    print(json.dumps(places, indent=2))
