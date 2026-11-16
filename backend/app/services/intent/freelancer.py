"""Freelancer.com: active projects via the public projects API (no login)."""

from datetime import datetime, timedelta
import time

import httpx

from app.core.config import settings
from app.services.intent.base import RawPost, from_unix, raise_for_rate_limit

SOURCE = "freelancer"
API_URL = "https://www.freelancer.com/api/projects/0.1/projects/active/"
PROJECT_URL = "https://www.freelancer.com/projects/"
PAGE_SIZE = 50
PAGE_GAP_S = 1.0


def parse_projects(payload: dict) -> list[RawPost]:
    projects = (payload.get("result") or {}).get("projects") or []
    posts = []
    for p in projects:
        if not p.get("id") or not p.get("title"):
            continue
        currency = p.get("currency") or {}
        budget = p.get("budget") or {}
        jobs = [j.get("name") for j in (p.get("jobs") or []) if j.get("name")]
        posts.append(
            RawPost(
                source=SOURCE,
                external_id=str(p["id"]),
                url=PROJECT_URL + (p.get("seo_url") or str(p["id"])),
                title=p["title"].strip(),
                body=(p.get("description") or p.get("preview_description") or "").strip(),
                channel=", ".join(jobs[:4]) or None,
                posted_at=from_unix(p.get("time_submitted")),
                budget_min=budget.get("minimum"),
                budget_max=budget.get("maximum"),
                currency=currency.get("code"),
                usd_rate=currency.get("exchange_rate"),
                bid_count=(p.get("bid_stats") or {}).get("bid_count"),
                hints={"project_type": p.get("type"), "country": currency.get("country")},
            )
        )
    return posts


def fetch(client: httpx.Client, since: datetime | None = None) -> list[RawPost]:
    """Newest projects per query, paging back to `since` when Klados was off.

    Without `since` (first run) a single page per query is read. With it,
    pages continue until they reach projects older than `since`, capped at
    FREELANCER_MAX_PAGES, so a day away is caught up in one pass.
    """
    # A little overlap so projects posted during the last pass aren't missed
    cutoff = since - timedelta(minutes=15) if since else None
    max_pages = settings.FREELANCER_MAX_PAGES if cutoff else 1
    seen: dict[str, RawPost] = {}
    for query in settings.FREELANCER_QUERIES:
        for page in range(max_pages):
            if page:
                time.sleep(PAGE_GAP_S)
            res = client.get(
                API_URL,
                params={
                    "query": query,
                    "limit": PAGE_SIZE,
                    "offset": page * PAGE_SIZE,
                    "full_description": "true",
                    "job_details": "true",
                },
            )
            raise_for_rate_limit(res, SOURCE)
            batch = parse_projects(res.json())
            for post in batch:
                seen.setdefault(post.external_id, post)
            dated = [p.posted_at for p in batch if p.posted_at]
            if len(batch) < PAGE_SIZE or not cutoff or (dated and min(dated) < cutoff):
                break
    return list(seen.values())
