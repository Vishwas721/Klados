"""Google Maps business discovery via a Camoufox-driven headless browser.

The Maps search sidebar is a single-page app: results are lazy-loaded into
a `div[role="feed"]` as the user scrolls, built from JS-side session tokens
that a plain HTTP GET can't reproduce (confirmed by capturing the page's own
XHR traffic - the `tbm=map` request it issues is signed with a short-lived
session id minted by the page's JS). So instead of hitting that endpoint
directly, we drive an actual (stealth) browser and read the rendered DOM.
"""

import asyncio
import logging
import os
from pathlib import Path
import random
import re
import sys
import time
from urllib.parse import quote, urlparse

# Ensure backend root is on sys.path when executed directly as a script
_backend_root = str(Path(__file__).resolve().parents[3])
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)

from camoufox.async_api import AsyncCamoufox

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session

from app.core.browser import camoufox_headless_mode
from app.db.models import Lead
from app.services.discovery.geo_grid import cell_to_coords, generate_city_cells

MAPS_SEARCH_URL = "https://www.google.com/maps/search/{query}/@{lat},{lng},15z"

logger = logging.getLogger(__name__)

# Screenshots + HTML of pages where the results feed never appeared, so a
# silent empty scrape can be diagnosed after the fact.
DEBUG_DUMP_DIR = Path(
    os.environ.get("GMAPS_DEBUG_DIR", Path(__file__).resolve().parents[4] / "logs" / "gmaps_debug")
)


def _extract_place_id(href: str | None) -> str | None:
    """Extract canonical Google Place ID (ChIJ...) or CID (0x...:0x...) from Maps URL."""
    if not href:
        return None
    m = re.search(r"(ChIJ[a-zA-Z0-9_\-]+)", href)
    if m:
        return m.group(1)
    m = re.search(r"!1s(0x[0-9a-fA-F]+:0x[0-9a-fA-F]+)", href)
    if m:
        return m.group(1)
    return None


def is_duplicate_lead(
    db: Session,
    phone_number: str | None,
    business_name: str,
    city: str | None = None,
    place_id: str | None = None,
) -> bool:
    """Check PostgreSQL for an existing place_id, phone_number or matching (business_name, city).

    Returns True if a lead already exists, meaning audit can be skipped.
    """
    if place_id and place_id.strip():
        stmt_pid = select(Lead.id).where(Lead.place_id == place_id.strip()).limit(1)
        if db.execute(stmt_pid).scalar_one_or_none() is not None:
            return True

    if not business_name:
        return False

    conditions = []
    if phone_number and phone_number.strip():
        conditions.append(Lead.phone_number == phone_number.strip())

    b_name = business_name.strip().lower()
    if city and city.strip():
        c_name = city.strip().lower()
        conditions.append(
            and_(
                func.lower(Lead.business_name) == b_name,
                func.lower(Lead.city) == c_name,
            )
        )
    else:
        conditions.append(func.lower(Lead.business_name) == b_name)

    if not conditions:
        return False

    stmt = select(Lead.id).where(or_(*conditions)).limit(1)
    return db.execute(stmt).scalar_one_or_none() is not None


FEED_SELECTOR = 'div[role="feed"]'
CARD_SELECTOR = 'div[role="article"]'
NAME_LINK_SELECTOR = "a.hfpxzc"
WEBSITE_LINK_SELECTOR = 'a[data-value="Website"]'
# Search-result cards no longer carry phone numbers or a Website button, so
# those come from each place's detail page instead.
DETAIL_PHONE_SELECTOR = 'button[data-item-id^="phone:tel:"]'
DETAIL_WEBSITE_SELECTOR = 'a[data-item-id="authority"]'

# Match Indian mobile numbers (starts with 6-9, 10 digits) or landline numbers (STD code + number, 10-11 digits)
PHONE_REGEX = re.compile(r"^[6-9]\d{9}$|^0[1-9]\d{8,9}$|^[1-9]\d{9}$")
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
    elif digits.startswith("0") and len(digits) == 11 and digits[1] in "6789":
        # Mobile with leading 0
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


async def _extract_from_feed(
    page, query_url: str, fallback_coords: tuple, limit: int, city: str = "Bengaluru"
) -> list:
    cards = page.locator(CARD_SELECTOR)
    count = await cards.count()
    logger.info("[gmaps] %d result cards rendered in feed", count)

    results = []
    seen_names = set()
    for i in range(count):
        card = cards.nth(i)

        name_link = card.locator(NAME_LINK_SELECTOR).first
        if await name_link.count() == 0:
            logger.info("[gmaps] card %d: skipped - no name link (%s)", i, NAME_LINK_SELECTOR)
            continue

        business_name = (await name_link.get_attribute("aria-label") or "").strip()
        if not business_name:
            logger.info("[gmaps] card %d: skipped - name link has empty aria-label", i)
            continue
        if business_name in seen_names:
            logger.info("[gmaps] card %d: skipped - duplicate name '%s'", i, business_name)
            continue

        place_href = await name_link.get_attribute("href")
        place_id = _extract_place_id(place_href)
        latitude, longitude = _extract_coords(place_href, fallback_coords)

        website_link = card.locator(WEBSITE_LINK_SELECTOR).first
        website_url = None
        if await website_link.count() > 0:
            href = await website_link.get_attribute("href")
            if _is_valid_website(href):
                website_url = href

        card_text = await card.inner_text()
        phone_number = _extract_phone(card_text)
        logger.info(
            "[gmaps] card %d: '%s' (place_id=%s) phone=%s website=%s",
            i,
            business_name,
            place_id,
            phone_number,
            website_url,
        )
        if phone_number is None:
            logger.debug("[gmaps] card %d text (no phone matched): %r", i, card_text)

        seen_names.add(business_name)
        results.append(
            {
                "place_id": place_id,
                "business_name": business_name,
                "phone_number": phone_number,
                "website_url": website_url,
                "city": city,
                "origin_source_url": query_url,
                "place_url": place_href,
                "latitude": latitude,
                "longitude": longitude,
                "category": "DIGITAL_GHOST" if website_url is None else None,
            }
        )
        if len(results) >= limit:
            break

    logger.info(
        "[gmaps] parsed %d places (%d with phone, %d with website) from %d cards",
        len(results),
        sum(1 for r in results if r["phone_number"]),
        sum(1 for r in results if r["website_url"]),
        count,
    )
    return results


async def _enrich_from_place_page(page, place: dict) -> None:
    """Fill in phone/website from the place's detail page when the card lacked them."""
    place_url = place.get("place_url")
    if not place_url or (place["phone_number"] and place["website_url"]):
        return

    # Mimic human pacing: random 3-7s delay between page navigations
    pacing_delay = random.uniform(3.0, 7.0)
    logger.info(
        "[gmaps] Mimicking human pacing: sleeping %.2fs before navigating to '%s' detail...",
        pacing_delay,
        place["business_name"],
    )
    await asyncio.sleep(pacing_delay)

    try:
        await page.goto(place_url, wait_until="domcontentloaded", timeout=30000)
        # Attempt to capture place_id from redirected detail URL if missing
        if not place.get("place_id"):
            place["place_id"] = _extract_place_id(page.url)

        await page.wait_for_selector(
            f"{DETAIL_PHONE_SELECTOR}, {DETAIL_WEBSITE_SELECTOR}, h1", timeout=10000
        )
        # The info rows render slightly after the heading.
        await page.wait_for_timeout(1000)
    except Exception as exc:
        logger.warning("[gmaps] detail page failed for '%s': %s", place["business_name"], exc)
        return

    if not place["phone_number"]:
        phone_button = page.locator(DETAIL_PHONE_SELECTOR).first
        if await phone_button.count() > 0:
            raw = (await phone_button.get_attribute("data-item-id") or "").removeprefix("phone:tel:")
            place["phone_number"] = _normalize_phone(raw)
            if place["phone_number"] is None:
                logger.info("[gmaps] '%s': phone %r failed normalization", place["business_name"], raw)

    if not place["website_url"]:
        website_link = page.locator(DETAIL_WEBSITE_SELECTOR).first
        if await website_link.count() > 0:
            href = await website_link.get_attribute("href")
            if _is_valid_website(href):
                place["website_url"] = href
                place["category"] = None
            else:
                logger.info("[gmaps] '%s': website %r rejected", place["business_name"], href)

    logger.info(
        "[gmaps] detail '%s': phone=%s website=%s",
        place["business_name"],
        place["phone_number"],
        place["website_url"],
    )


async def _diagnose_missing_feed(page) -> str:
    """Explain why the results feed never rendered, and dump the page."""
    current_url = page.url
    try:
        title = await page.title()
        body_text = (await page.locator("body").inner_text(timeout=5000))[:2000]
    except Exception as exc:
        title, body_text = "?", f"<could not read body: {exc}>"

    lowered = body_text.lower()
    if "consent.google" in current_url or "before you continue" in lowered:
        reason = "Google consent interstitial"
    elif "/sorry/" in current_url or "unusual traffic" in lowered or "captcha" in lowered:
        reason = "Google bot check / CAPTCHA"
    elif "/maps/place/" in current_url:
        reason = "Maps jumped straight to a single place page (no results list)"
    else:
        reason = "feed selector not found (selectors may be stale)"

    dump_hint = ""
    try:
        DEBUG_DUMP_DIR.mkdir(parents=True, exist_ok=True)
        stem = DEBUG_DUMP_DIR / f"no_feed_{int(time.time())}"
        await page.screenshot(path=f"{stem}.png", full_page=True)
        Path(f"{stem}.html").write_text(await page.content(), encoding="utf-8")
        dump_hint = f" (dumped {stem}.png/.html)"
    except Exception as exc:
        dump_hint = f" (debug dump failed: {exc})"

    logger.warning(
        "[gmaps] no results feed: %s | url=%s | title=%r%s | body[:300]=%r",
        reason,
        current_url,
        title,
        dump_hint,
        body_text[:300],
    )
    return reason


async def _extract_places_async(
    query: str, lat: float, lng: float, limit: int, city: str = "Bengaluru"
) -> list:
    url = MAPS_SEARCH_URL.format(query=quote(query), lat=lat, lng=lng)

    camoufox = AsyncCamoufox(headless=camoufox_headless_mode(), geoip=True, locale="en-IN")
    launched = False
    try:
        browser = await camoufox.__aenter__()
        launched = True
        page = await browser.new_page()
        logger.info("[gmaps] loading %s", url)
        await page.goto(url, wait_until="networkidle", timeout=45000)
        logger.info("[gmaps] landed on %s (title=%r)", page.url, await page.title())

        try:
            await page.wait_for_selector(FEED_SELECTOR, timeout=15000)
        except Exception:
            await _diagnose_missing_feed(page)
            return []

        await _scroll_feed(page, target_count=limit)
        places = await _extract_from_feed(page, url, (lat, lng), limit, city=city)

        detail_page = await browser.new_page()
        for place in places:
            await _enrich_from_place_page(detail_page, place)
        logger.info(
            "[gmaps] after detail pages: %d/%d with phone, %d/%d with website",
            sum(1 for p in places if p["phone_number"]),
            len(places),
            sum(1 for p in places if p["website_url"]),
            len(places),
        )
        return places
    finally:
        if launched:
            await camoufox.__aexit__(None, None, None)


def extract_places(
    query: str, lat: float, lng: float, limit: int = 20, city: str = "Bengaluru"
) -> list:
    """Search Google Maps around (lat, lng) and return parsed business leads."""
    return asyncio.run(_extract_places_async(query, lat, lng, limit, city=city))



if __name__ == "__main__":
    import json

    cell = generate_city_cells("Bengaluru")[0]
    cell_lat, cell_lng = cell_to_coords(cell)

    places = extract_places("dental clinic", cell_lat, cell_lng, limit=20)
    print(json.dumps(places, indent=2))
