"""Any RSS 2.0 / Atom feed of job or request posts (INTENT_RSS_FEEDS)."""

from email.utils import parsedate_to_datetime
from urllib.parse import urlparse
import xml.etree.ElementTree as ET

import httpx

from app.core.config import settings
from app.services.intent.base import (
    RawPost,
    SourceNotConfigured,
    html_to_text,
    parse_iso,
    raise_for_rate_limit,
    stable_id,
)

SOURCE = "rss"
ATOM = "{http://www.w3.org/2005/Atom}"


def _rfc822(value: str | None):
    if not value:
        return None
    try:
        return parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return parse_iso(value)


def parse_feed(xml_text: str, feed_url: str) -> list[RawPost]:
    root = ET.fromstring(xml_text)
    channel = urlparse(feed_url).netloc.removeprefix("www.")
    posts = []

    for item in root.iter("item"):  # RSS 2.0
        title = (item.findtext("title") or "").strip()
        link = (item.findtext("link") or "").strip()
        if not title or not link:
            continue
        key = (item.findtext("guid") or link).strip()
        posts.append(
            RawPost(
                source=SOURCE,
                external_id=stable_id(key),
                url=link,
                title=title,
                body=html_to_text(item.findtext("description")),
                author=(item.findtext("author") or item.findtext("{http://purl.org/dc/elements/1.1/}creator")),
                channel=channel,
                posted_at=_rfc822(item.findtext("pubDate")),
            )
        )

    for entry in root.iter(f"{ATOM}entry"):  # Atom
        title = (entry.findtext(f"{ATOM}title") or "").strip()
        link_el = entry.find(f"{ATOM}link")
        link = link_el.get("href", "") if link_el is not None else ""
        if not title or not link:
            continue
        key = (entry.findtext(f"{ATOM}id") or link).strip()
        posts.append(
            RawPost(
                source=SOURCE,
                external_id=stable_id(key),
                url=link,
                title=title,
                body=html_to_text(entry.findtext(f"{ATOM}content") or entry.findtext(f"{ATOM}summary")),
                author=entry.findtext(f"{ATOM}author/{ATOM}name"),
                channel=channel,
                posted_at=parse_iso(entry.findtext(f"{ATOM}published") or entry.findtext(f"{ATOM}updated")),
            )
        )
    return posts


def is_configured() -> bool:
    return bool(settings.INTENT_RSS_FEEDS)


def fetch(client: httpx.Client) -> list[RawPost]:
    if not is_configured():
        raise SourceNotConfigured("Add feed URLs to INTENT_RSS_FEEDS")
    posts: list[RawPost] = []
    errors = []
    for feed_url in settings.INTENT_RSS_FEEDS:
        try:
            res = client.get(feed_url)
            raise_for_rate_limit(res, SOURCE)
            posts.extend(parse_feed(res.text, feed_url))
        except (httpx.HTTPError, ET.ParseError) as exc:
            # One broken feed shouldn't hide the others
            errors.append(f"{feed_url}: {exc}")
    if errors and not posts:
        raise RuntimeError("; ".join(errors)[:500])
    return posts
