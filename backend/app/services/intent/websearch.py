"""Open-web search for "need a website" posts through a self-hosted SearXNG.

SearXNG is free and runs in docker compose; it needs `json` enabled under
`search.formats` (see searxng/settings.yml). Results from sites another
source already covers are skipped.
"""

from urllib.parse import urlparse

import httpx

from app.core.config import settings
from app.services.intent.base import (
    RawPost,
    SourceNotConfigured,
    parse_iso,
    raise_for_rate_limit,
    stable_id,
)

SOURCE = "web"
COVERED_DOMAINS = ("freelancer.com", "reddit.com", "ycombinator.com")


def parse_results(payload: dict, query: str) -> list[RawPost]:
    posts = []
    for r in payload.get("results") or []:
        url = r.get("url") or ""
        title = (r.get("title") or "").strip()
        host = urlparse(url).netloc.lower().removeprefix("www.")
        if not url or not title or any(host.endswith(d) for d in COVERED_DOMAINS):
            continue
        posts.append(
            RawPost(
                source=SOURCE,
                external_id=stable_id(url),
                url=url,
                title=title,
                body=(r.get("content") or "").strip(),
                channel=host,
                posted_at=parse_iso(r.get("publishedDate")),
                hints={"query": query},
            )
        )
    return posts


def is_configured() -> bool:
    return bool(settings.SEARXNG_URL)


def fetch(client: httpx.Client) -> list[RawPost]:
    if not is_configured():
        raise SourceNotConfigured("Set SEARXNG_URL (docker compose runs one on :8888)")
    base = settings.SEARXNG_URL.rstrip("/")
    seen: dict[str, RawPost] = {}
    for query in settings.WEB_SEARCH_QUERIES:
        res = client.get(
            f"{base}/search",
            params={"q": query, "format": "json", "time_range": "month"},
        )
        raise_for_rate_limit(res, SOURCE)
        for post in parse_results(res.json(), query):
            seen.setdefault(post.external_id, post)
    return list(seen.values())
