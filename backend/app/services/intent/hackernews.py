"""Hacker News: the monthly "Freelancer? Seeking freelancer?" thread.

Read through the free Algolia HN API. Most replies are freelancers offering
work; only the "SEEKING FREELANCER" ones are clients, and scoring keeps
just those.
"""

import httpx

from app.services.intent.base import RawPost, from_unix, html_to_text, raise_for_rate_limit

SOURCE = "hackernews"
ALGOLIA = "https://hn.algolia.com/api/v1"
THREAD_TITLE = "Ask HN: Freelancer? Seeking freelancer?"


def latest_thread_id(client: httpx.Client) -> int | None:
    res = client.get(
        f"{ALGOLIA}/search_by_date",
        params={"query": '"Seeking freelancer"', "tags": "story", "hitsPerPage": 20},
    )
    raise_for_rate_limit(res, SOURCE)
    for hit in res.json().get("hits") or []:
        if (hit.get("title") or "").startswith(THREAD_TITLE):
            return int(hit["objectID"])
    return None


def parse_thread(payload: dict) -> list[RawPost]:
    thread = payload.get("title") or "HN freelancer thread"
    posts = []
    for child in payload.get("children") or []:
        text = html_to_text(child.get("text"))
        if not text or not child.get("id"):
            continue
        first_line = text.splitlines()[0]
        posts.append(
            RawPost(
                source=SOURCE,
                external_id=str(child["id"]),
                url=f"https://news.ycombinator.com/item?id={child['id']}",
                title=first_line[:200],
                body=text,
                author=child.get("author"),
                channel=thread.removeprefix("Ask HN: ").strip(),
                posted_at=from_unix(child.get("created_at_i")),
            )
        )
    return posts


def fetch(client: httpx.Client) -> list[RawPost]:
    thread_id = latest_thread_id(client)
    if thread_id is None:
        return []
    res = client.get(f"{ALGOLIA}/items/{thread_id}")
    raise_for_rate_limit(res, SOURCE)
    return parse_thread(res.json())
