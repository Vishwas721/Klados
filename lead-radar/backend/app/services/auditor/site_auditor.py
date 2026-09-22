"""Website performance/UX audit worker driven by a Camoufox headless browser.

Categorizes a lead's website into a funnel bucket so downstream outreach can
be tailored to what's actually broken instead of treating every lead the
same: DIGITAL_GHOST (no site), DIGITAL_DINOSAUR (no HTTPS or not mobile
responsive), LAGGY_UX (loads too slowly), AUTOMATION_CANDIDATE (a healthy
site worth checking for missing booking/chat automation).
"""

import asyncio
from pathlib import Path
import sys

# Ensure backend root is on sys.path when executed directly as a script
_backend_root = str(Path(__file__).resolve().parents[3])
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)

from camoufox.async_api import AsyncCamoufox
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.services.auditor.classifier import query_ollama

NAV_TIMEOUT_MS = 15000
DOM_LOAD_TIME_THRESHOLD_MS = 4500
TTFB_THRESHOLD_MS = 1800

_PERFORMANCE_JS = """
() => {
    const nav = performance.getEntriesByType('navigation')[0];
    if (!nav) return null;
    return {
        ttfb_ms: nav.responseStart,
        dom_load_time_ms: nav.domContentLoadedEventEnd,
    };
}
"""


async def _audit_lead_async(website_url: str) -> dict:
    has_ssl = website_url.startswith("https://")

    camoufox = AsyncCamoufox(headless="virtual", geoip=True, humanize=True, os=["windows"])
    launched = False
    try:
        browser = await camoufox.__aenter__()
        launched = True
        page = await browser.new_page()

        try:
            await page.goto(website_url, timeout=NAV_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            # A site that can't finish loading within the strict timeout is,
            # by definition, laggy - categorize it rather than blow up the run.
            return {
                "category": "LAGGY_UX",
                "has_ssl": has_ssl,
                "is_mobile_responsive": None,
                "ttfb_ms": None,
                "dom_load_time_ms": None,
            }

        metrics = await page.evaluate(_PERFORMANCE_JS) or {}
        ttfb_ms = metrics.get("ttfb_ms", 0.0)
        dom_load_time_ms = metrics.get("dom_load_time_ms", 0.0)

        is_mobile_responsive = await page.locator("meta[name='viewport']").count() > 0

        if not has_ssl or not is_mobile_responsive:
            return {
                "category": "DIGITAL_DINOSAUR",
                "has_ssl": has_ssl,
                "is_mobile_responsive": is_mobile_responsive,
                "ttfb_ms": ttfb_ms,
                "dom_load_time_ms": dom_load_time_ms,
            }

        if dom_load_time_ms > DOM_LOAD_TIME_THRESHOLD_MS or ttfb_ms > TTFB_THRESHOLD_MS:
            return {
                "category": "LAGGY_UX",
                "has_ssl": has_ssl,
                "is_mobile_responsive": is_mobile_responsive,
                "ttfb_ms": ttfb_ms,
                "dom_load_time_ms": dom_load_time_ms,
            }

        body_text = await page.inner_text("body")
        findings = query_ollama(body_text)

        return {
            "category": "AUTOMATION_CANDIDATE",
            "has_ssl": has_ssl,
            "is_mobile_responsive": is_mobile_responsive,
            "ttfb_ms": ttfb_ms,
            "dom_load_time_ms": dom_load_time_ms,
            **findings,
        }
    finally:
        if launched:
            await camoufox.__aexit__(None, None, None)


def audit_lead(website_url: str | None) -> dict:
    """Audit a lead's website and categorize it for outreach prioritization."""
    if not website_url:
        return {"category": "DIGITAL_GHOST"}

    return asyncio.run(_audit_lead_async(website_url))


if __name__ == "__main__":
    import json

    print(json.dumps(audit_lead("https://example.com"), indent=2))
