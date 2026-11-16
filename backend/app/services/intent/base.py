"""Shared pieces for the request-radar sources."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
import html
import re

import httpx

from app.core.config import settings


class SourceRateLimited(Exception):
    """The source asked us to slow down; back off for retry_after seconds."""

    def __init__(self, source: str, retry_after: int = 1800):
        super().__init__(f"{source} rate-limited us; backing off {retry_after}s")
        self.retry_after = retry_after


class SourceNotConfigured(Exception):
    """The source needs settings (a URL, a key…) that aren't set."""


@dataclass
class RawPost:
    source: str
    external_id: str
    url: str
    title: str
    body: str = ""
    author: str | None = None
    channel: str | None = None
    posted_at: datetime | None = None
    budget_min: float | None = None
    budget_max: float | None = None
    currency: str | None = None
    # Multiply a budget in `currency` by this to get USD, when the source says
    usd_rate: float | None = None
    bid_count: int | None = None
    # Source-specific hints for scoring, e.g. {"tag": "hiring"}
    hints: dict = field(default_factory=dict)


def make_client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": settings.INTENT_USER_AGENT},
        timeout=httpx.Timeout(20.0),
        follow_redirects=True,
    )


def raise_for_rate_limit(res: httpx.Response, source: str) -> None:
    if res.status_code == 429:
        try:
            retry_after = int(res.headers.get("Retry-After", "1800"))
        except ValueError:
            retry_after = 1800
        raise SourceRateLimited(source, max(retry_after, 300))
    res.raise_for_status()


_TAG_RE = re.compile(r"<[^>]+>")
_BLOCK_TAG_RE = re.compile(r"<\s*(br|/p|p|/div|/li|li|/h\d|pre|/pre)\b[^>]*>", re.IGNORECASE)
_SPACE_RE = re.compile(r"[ \t\f\v]+")
_MULTI_NL_RE = re.compile(r"\n{3,}")


def html_to_text(raw: str | None) -> str:
    """Rough HTML → plain text that keeps paragraph breaks."""
    if not raw:
        return ""
    text = _BLOCK_TAG_RE.sub("\n", raw)
    text = _TAG_RE.sub("", text)
    text = html.unescape(text)
    text = "\n".join(_SPACE_RE.sub(" ", line).strip() for line in text.splitlines())
    return _MULTI_NL_RE.sub("\n\n", text).strip()


def stable_id(value: str) -> str:
    """A short fixed-length id for sources whose natural key is a long URL."""
    return hashlib.sha1(value.encode("utf-8")).hexdigest()


def from_unix(ts: float | int | None) -> datetime | None:
    if ts is None:
        return None
    try:
        return datetime.fromtimestamp(float(ts), tz=timezone.utc)
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
