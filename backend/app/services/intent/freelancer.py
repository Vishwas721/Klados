"""Freelancer.com: active projects via the public projects API (no login)."""

import httpx

from app.core.config import settings
from app.services.intent.base import RawPost, from_unix, raise_for_rate_limit

SOURCE = "freelancer"
API_URL = "https://www.freelancer.com/api/projects/0.1/projects/active/"
PROJECT_URL = "https://www.freelancer.com/projects/"


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


def fetch(client: httpx.Client) -> list[RawPost]:
    seen: dict[str, RawPost] = {}
    for query in settings.FREELANCER_QUERIES:
        res = client.get(
            API_URL,
            params={
                "query": query,
                "limit": 50,
                "full_description": "true",
                "job_details": "true",
            },
        )
        raise_for_rate_limit(res, SOURCE)
        for post in parse_projects(res.json()):
            seen.setdefault(post.external_id, post)
    return list(seen.values())
