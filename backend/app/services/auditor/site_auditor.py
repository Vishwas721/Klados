"""Website performance/UX audit worker driven by a Camoufox headless browser.

Categorizes a lead's website into a funnel bucket so downstream outreach can
be tailored to what's actually broken instead of treating every lead the
same: DIGITAL_GHOST (no site, or a site that doesn't resolve), DIGITAL_DINOSAUR
(no HTTPS or not mobile responsive), LAGGY_UX (loads too slowly),
AUTOMATION_CANDIDATE (a healthy site worth checking for missing booking/chat
automation).
"""

import asyncio
from pathlib import Path
import sys
import time

# Ensure backend root is on sys.path when executed directly as a script
_backend_root = str(Path(__file__).resolve().parents[3])
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)

from camoufox.async_api import AsyncCamoufox
from playwright.async_api import Error as PlaywrightError
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from app.core.browser import camoufox_headless_mode
from app.services.auditor.classifier import query_ollama
from app.services.auditor.tech_detector import detect_stack

NAV_TIMEOUT_MS = 15000
DOM_LOAD_TIME_THRESHOLD_MS = 4500
TTFB_THRESHOLD_MS = 1800

# Navigation errors meaning the site itself is gone, not merely slow
_UNREACHABLE_MARKERS = (
    "NS_ERROR_UNKNOWN_HOST",
    "NS_ERROR_CONNECTION_REFUSED",
    "NS_ERROR_NET_RESET",
    "NS_ERROR_NET_INTERRUPT",
    "SSL_ERROR",
    "SEC_ERROR",
    "ERR_NAME_NOT_RESOLVED",
    "ERR_CONNECTION_REFUSED",
)

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


def classify_site(
    has_ssl: bool, is_mobile_responsive: bool, ttfb_ms: float, dom_load_time_ms: float
) -> str:
    """Bucket a site that loaded, in strict priority order."""
    if not has_ssl or not is_mobile_responsive:
        return "DIGITAL_DINOSAUR"
    if dom_load_time_ms > DOM_LOAD_TIME_THRESHOLD_MS or ttfb_ms > TTFB_THRESHOLD_MS:
        return "LAGGY_UX"
    return "AUTOMATION_CANDIDATE"


def describe_unreachable(error_message: str) -> str | None:
    """Short reason if a navigation error means the site is down, else None."""
    for marker in _UNREACHABLE_MARKERS:
        if marker in error_message:
            return f"Website unreachable ({marker})"
    return None


async def _audit_page(page, website_url: str) -> dict:
    started = time.monotonic()
    try:
        await page.goto(website_url, timeout=NAV_TIMEOUT_MS)
    except PlaywrightTimeoutError:
        # A site that can't finish loading within the strict timeout is,
        # by definition, laggy - categorize it rather than blow up the run.
        try:
            partial_html = await page.content()
        except PlaywrightError:
            partial_html = None
        return {
            "category": "LAGGY_UX",
            "has_ssl": page.url.startswith("https://"),
            "is_mobile_responsive": None,
            "ttfb_ms": None,
            "dom_load_time_ms": NAV_TIMEOUT_MS,
            "operational_bottleneck": f"Site did not finish loading within {NAV_TIMEOUT_MS // 1000}s",
            **detect_stack(partial_html),
        }
    except PlaywrightError as exc:
        reason = describe_unreachable(str(exc))
        if reason is None:
            raise
        # A listed website that doesn't resolve is as good as no website
        return {
            "category": "DIGITAL_GHOST",
            "has_ssl": False,
            "is_mobile_responsive": False,
            "ttfb_ms": 0,
            "dom_load_time_ms": 0,
            "operational_bottleneck": reason,
        }
    elapsed_ms = (time.monotonic() - started) * 1000

    # Judge HTTPS on where we landed: many listings say http:// but redirect
    has_ssl = page.url.startswith("https://")

    # Navigation timing is occasionally missing or zeroed by SPA routers;
    # fall back to wall-clock time rather than scoring the site as instant.
    metrics = await page.evaluate(_PERFORMANCE_JS) or {}
    ttfb_ms = metrics.get("ttfb_ms") or 0.0
    dom_load_time_ms = metrics.get("dom_load_time_ms") or elapsed_ms

    is_mobile_responsive = await page.locator("meta[name='viewport']").count() > 0
    stack = detect_stack(await page.content())

    category = classify_site(has_ssl, is_mobile_responsive, ttfb_ms, dom_load_time_ms)
    result = {
        "category": category,
        "has_ssl": has_ssl,
        "is_mobile_responsive": is_mobile_responsive,
        "ttfb_ms": ttfb_ms,
        "dom_load_time_ms": dom_load_time_ms,
        **stack,
    }

    if category == "AUTOMATION_CANDIDATE":
        findings = query_ollama(await page.inner_text("body"))
        # Markup evidence wins; the LLM can only add what the HTML missed
        result["has_chat_widget"] = stack["has_chat_widget"] or findings["has_chat_widget"]
        result["has_online_booking"] = stack["has_online_booking"] or findings["has_online_booking"]
        result["operational_bottleneck"] = findings["operational_bottleneck"]

    return result


class SiteAuditor:
    """Audits many sites with one shared browser.

    Launching Camoufox takes seconds, so a batch reuses one browser and gives
    each site a fresh page (its own context, so no cookies leak between
    sites). The browser starts lazily on the first site, so a batch of
    website-less leads never launches one, and is relaunched if it dies.
    Use as a context manager so the browser is always shut down.
    """

    def __init__(self):
        self._loop: asyncio.AbstractEventLoop | None = None
        self._camoufox = None
        self._browser = None

    def __enter__(self) -> "SiteAuditor":
        return self

    def __exit__(self, *exc_info) -> None:
        self.close()

    def audit(self, website_url: str | None) -> dict:
        """Audit a lead's website and categorize it for outreach prioritization."""
        if not website_url:
            return {"category": "DIGITAL_GHOST"}
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
        return self._loop.run_until_complete(self._audit(website_url))

    def close(self) -> None:
        if self._loop is None:
            return
        self._loop.run_until_complete(self._close_browser())
        self._loop.close()
        self._loop = None

    async def _audit(self, website_url: str) -> dict:
        browser = await self._ensure_browser()
        page = await browser.new_page()
        try:
            return await _audit_page(page, website_url)
        finally:
            try:
                await page.close()
            except PlaywrightError:
                pass

    async def _ensure_browser(self):
        if self._browser is None or not self._browser.is_connected():
            await self._close_browser()
            self._camoufox = AsyncCamoufox(
                headless=camoufox_headless_mode(), geoip=True, humanize=True, os=["windows"]
            )
            self._browser = await self._camoufox.__aenter__()
        return self._browser

    async def _close_browser(self) -> None:
        if self._camoufox is not None:
            try:
                await self._camoufox.__aexit__(None, None, None)
            except Exception:
                pass  # already dead; nothing left to clean up
        self._camoufox = None
        self._browser = None


def audit_lead(website_url: str | None) -> dict:
    """One-off audit; batches should share a SiteAuditor instead."""
    with SiteAuditor() as auditor:
        return auditor.audit(website_url)


if __name__ == "__main__":
    import json

    print(json.dumps(audit_lead("https://example.com"), indent=2))
