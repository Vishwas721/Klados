"""Reddit: newest posts across the configured subreddits.

Uses the official API when REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET are set
(a free "script" app), otherwise the public Atom feed. The feed needs no
setup but Reddit rate-limits it hard, so the poller backs off on a 429.
"""

import re
import time
import xml.etree.ElementTree as ET

import httpx

from app.core.config import settings
from app.services.intent.base import (
    RawPost,
    SourceRateLimited,
    from_unix,
    html_to_text,
    parse_iso,
    raise_for_rate_limit,
)

SOURCE = "reddit"
ATOM = "{http://www.w3.org/2005/Atom}"
ANON_GAP_S = 5
_SUBMITTED_BY_RE = re.compile(r"\s*submitted by\s+/u/.*$", re.IGNORECASE | re.DOTALL)


def parse_atom(xml_text: str) -> list[RawPost]:
    root = ET.fromstring(xml_text)
    posts = []
    for entry in root.findall(f"{ATOM}entry"):
        entry_id = (entry.findtext(f"{ATOM}id") or "").strip()
        title = (entry.findtext(f"{ATOM}title") or "").strip()
        link = entry.find(f"{ATOM}link")
        if not entry_id or not title or link is None:
            continue
        category = entry.find(f"{ATOM}category")
        body = html_to_text(entry.findtext(f"{ATOM}content"))
        body = _SUBMITTED_BY_RE.sub("", body).strip()
        author = (entry.findtext(f"{ATOM}author/{ATOM}name") or "").removeprefix("/u/") or None
        posts.append(
            RawPost(
                source=SOURCE,
                external_id=entry_id.removeprefix("t3_"),
                url=link.get("href", ""),
                title=title,
                body=body,
                author=author,
                channel=f"r/{category.get('term')}" if category is not None else None,
                posted_at=parse_iso(entry.findtext(f"{ATOM}published") or entry.findtext(f"{ATOM}updated")),
            )
        )
    return posts


def parse_listing(payload: dict) -> list[RawPost]:
    posts = []
    for child in (payload.get("data") or {}).get("children") or []:
        d = child.get("data") or {}
        if not d.get("id") or not d.get("title"):
            continue
        posts.append(
            RawPost(
                source=SOURCE,
                external_id=d["id"],
                url="https://www.reddit.com" + d.get("permalink", ""),
                title=d["title"].strip(),
                body=(d.get("selftext") or "").strip(),
                author=d.get("author"),
                channel=f"r/{d.get('subreddit')}",
                posted_at=from_unix(d.get("created_utc")),
                hints={"flair": d.get("link_flair_text")},
            )
        )
    return posts


def _oauth_token(client: httpx.Client) -> str:
    res = client.post(
        "https://www.reddit.com/api/v1/access_token",
        data={"grant_type": "client_credentials"},
        auth=(settings.REDDIT_CLIENT_ID or "", settings.REDDIT_CLIENT_SECRET or ""),
    )
    raise_for_rate_limit(res, SOURCE)
    return res.json()["access_token"]


def _fetch_group(client: httpx.Client, subs: str, token: str | None) -> list[RawPost]:
    if token:
        res = client.get(
            f"https://oauth.reddit.com/r/{subs}/new",
            params={"limit": 100, "raw_json": 1},
            headers={"Authorization": f"Bearer {token}"},
        )
        raise_for_rate_limit(res, SOURCE)
        return parse_listing(res.json())

    res = client.get(f"https://www.reddit.com/r/{subs}/new/.rss", params={"limit": 100})
    if res.status_code == 403:
        # Reddit answers blocked anonymous clients with 403 rather than 429
        raise SourceRateLimited(SOURCE, 3600)
    raise_for_rate_limit(res, SOURCE)
    return parse_atom(res.text)


def fetch(client: httpx.Client, since=None) -> list[RawPost]:
    token = None
    if settings.REDDIT_CLIENT_ID and settings.REDDIT_CLIENT_SECRET:
        token = _oauth_token(client)

    posts: list[RawPost] = []
    groups = [g for g in (settings.REDDIT_HIRING_SUBREDDITS, settings.REDDIT_COMMUNITY_SUBREDDITS) if g]
    for i, group in enumerate(groups):
        if i and not token:
            time.sleep(ANON_GAP_S)  # the anonymous feed throttles back-to-back requests
        posts.extend(_fetch_group(client, "+".join(group), token))
    return posts
