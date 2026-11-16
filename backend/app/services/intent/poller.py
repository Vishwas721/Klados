"""Poll request sources, score what comes back, and save new posts.

`poll_source(name)` is one pass over one source. The request-radar process
(app.intent_poller) calls it on each source's interval, or right away when
the dashboard asks via `request_poll`. Per-source state lives in Redis:
last run/result for the dashboard, a back-off key after a rate limit, and a
"poll now" flag.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import time
from typing import Callable

import httpx
from redis import Redis
from sqlalchemy import update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from app.core.config import settings
from app.db.models import IntentPost
from app.db.session import SessionLocal
from app.services.intent import freelancer, hackernews, reddit, rss, websearch
from app.services.intent.base import (
    RawPost,
    SourceNotConfigured,
    SourceRateLimited,
    make_client,
)
from app.services.intent.notify import alerts_enabled, send_alert
from app.services.intent.scoring import assess
from app.services.intent.writer import ollama_enrich, template_reply

logger = logging.getLogger(__name__)

# Ollama is slow; cap tailored write-ups per pass so one source can't stall the loop
MAX_LLM_PER_RUN = 8


@dataclass(frozen=True)
class SourceSpec:
    key: str
    label: str
    fetch: Callable[[httpx.Client], list[RawPost]]
    interval_s: Callable[[], int]
    is_configured: Callable[[], bool]
    setup_hint: str


SOURCES: dict[str, SourceSpec] = {
    s.key: s
    for s in [
        SourceSpec(
            "freelancer", "Freelancer.com", freelancer.fetch, lambda: settings.FREELANCER_POLL_S,
            lambda: True, "Public projects API, no setup needed.",
        ),
        SourceSpec(
            "reddit", "Reddit", reddit.fetch, lambda: settings.REDDIT_POLL_S, lambda: True,
            "Works without setup via RSS; add REDDIT_CLIENT_ID / REDDIT_CLIENT_SECRET to avoid rate limits.",
        ),
        SourceSpec(
            "hackernews", "Hacker News", hackernews.fetch, lambda: settings.HN_POLL_S, lambda: True,
            "Monthly 'Freelancer? Seeking freelancer?' thread, no setup needed.",
        ),
        SourceSpec(
            "rss", "RSS feeds", rss.fetch, lambda: settings.RSS_POLL_S, rss.is_configured,
            "Add job-board feed URLs to INTENT_RSS_FEEDS (JSON list).",
        ),
        SourceSpec(
            "web", "Open web", websearch.fetch, lambda: settings.WEB_POLL_S, websearch.is_configured,
            "Set SEARXNG_URL; docker compose runs SearXNG on http://localhost:8888.",
        ),
    ]
}


def _status_key(source: str) -> str:
    return f"intent:status:{source}"


def _backoff_key(source: str) -> str:
    return f"intent:backoff:{source}"


def _poll_now_key(source: str) -> str:
    return f"intent:poll_now:{source}"


def request_poll(r: Redis, source: str) -> None:
    r.set(_poll_now_key(source), "1", ex=3600)


def take_poll_request(r: Redis, source: str) -> bool:
    return bool(r.delete(_poll_now_key(source)))


def last_attempt_ts(r: Redis, source: str) -> float:
    val = r.hget(_status_key(source), "last_attempt_at")
    try:
        return datetime.fromisoformat(val.decode() if isinstance(val, bytes) else val).timestamp()
    except (TypeError, ValueError, AttributeError):
        return 0.0


def source_status(r: Redis, source: str) -> dict:
    raw = r.hgetall(_status_key(source)) or {}
    status = {
        (k.decode() if isinstance(k, bytes) else k): (v.decode() if isinstance(v, bytes) else v)
        for k, v in raw.items()
    }
    status["backoff_s"] = max(0, int(r.ttl(_backoff_key(source)) or 0))
    status["poll_requested"] = bool(r.exists(_poll_now_key(source)))
    return status


def _record(r: Redis, source: str, **fields) -> None:
    clean = {k: ("" if v is None else str(v)) for k, v in fields.items()}
    r.hset(_status_key(source), mapping=clean)


def _insert(db, raw: RawPost, assessment) -> IntentPost | None:
    values = {
        "source": raw.source,
        "external_id": raw.external_id[:255],
        "url": raw.url,
        "title": raw.title[:500],
        "body": raw.body[:20000],
        "author": (raw.author or None) and raw.author[:255],
        "channel": (raw.channel or None) and raw.channel[:255],
        "posted_at": raw.posted_at,
        "budget_min": raw.budget_min,
        "budget_max": raw.budget_max,
        "currency": raw.currency,
        "budget_usd": assessment.budget_usd,
        "bid_count": raw.bid_count,
        "fit": assessment.fit,
        "score": assessment.score,
        "signals": assessment.signals,
        "is_local": assessment.is_local,
        "reply_draft": template_reply(assessment.fit, raw.title, raw.author),
        "status": "NEW",
    }
    stmt = (
        pg_insert(IntentPost)
        .values(**values)
        .on_conflict_do_nothing(constraint="uq_intent_posts_source_external")
        .returning(IntentPost.id)
    )
    new_id = db.execute(stmt).scalar_one_or_none()
    return db.get(IntentPost, new_id) if new_id else None


def save_posts(db, posts: list[RawPost], now: datetime | None = None) -> list[IntentPost]:
    """Score posts and insert the new, relevant ones. Returns what was inserted."""
    now = now or datetime.now(timezone.utc)
    oldest = now - timedelta(days=settings.INTENT_MAX_AGE_DAYS)
    inserted = []
    for raw in posts:
        if raw.posted_at and raw.posted_at < oldest:
            continue
        assessment = assess(raw, now=now)
        if assessment is None or assessment.score < settings.INTENT_MIN_SCORE:
            continue
        row = _insert(db, raw, assessment)
        if row is not None:
            inserted.append(row)
    db.commit()
    return inserted


def enrich_and_alert(db, rows: list[IntentPost]) -> None:
    worth = sorted(
        (p for p in rows if p.score >= settings.INTENT_LLM_MIN_SCORE), key=lambda p: -p.score
    )[:MAX_LLM_PER_RUN]
    for post in worth:
        extra = ollama_enrich(post.title, post.body)
        if extra is None:
            break  # Ollama is down; don't wait out the timeout for every post
        post.summary = extra["summary"] or post.summary
        post.reply_draft = extra["reply"] or post.reply_draft
    db.commit()

    if not alerts_enabled():
        return
    for post in rows:
        if post.score >= settings.INTENT_ALERT_MIN_SCORE and send_alert(post):
            db.execute(update(IntentPost).where(IntentPost.id == post.id).values(alerted=True))
    db.commit()


def poll_source(name: str, r: Redis, session_factory=SessionLocal) -> dict:
    spec = SOURCES[name]
    started = time.monotonic()
    now = datetime.now(timezone.utc)
    _record(r, name, last_attempt_at=now.isoformat())

    if r.exists(_backoff_key(name)):
        return {"source": name, "status": "backing_off"}
    if not spec.is_configured():
        _record(r, name, last_error="", state="not_configured")
        return {"source": name, "status": "not_configured"}

    try:
        with make_client() as client:
            posts = spec.fetch(client)
    except SourceRateLimited as exc:
        r.set(_backoff_key(name), "1", ex=exc.retry_after)
        _record(r, name, last_error=str(exc), state="backing_off")
        logger.warning("[intent] %s", exc)
        return {"source": name, "status": "rate_limited"}
    except SourceNotConfigured as exc:
        _record(r, name, last_error="", state="not_configured")
        return {"source": name, "status": "not_configured", "detail": str(exc)}
    except Exception as exc:  # network errors, bad payloads: report, keep the loop alive
        message = f"{type(exc).__name__}: {str(exc).splitlines()[0][:300] if str(exc) else ''}"
        _record(r, name, last_error=message, state="error")
        logger.error("[intent] %s fetch failed: %s", name, message)
        return {"source": name, "status": "error", "detail": message}

    db = session_factory()
    try:
        inserted = save_posts(db, posts, now=now)
        enrich_and_alert(db, inserted)
    except Exception as exc:
        db.rollback()
        message = f"{type(exc).__name__}: {str(exc).splitlines()[0][:300] if str(exc) else ''}"
        _record(r, name, last_error=message, state="error")
        logger.error("[intent] %s save failed: %s", name, message)
        return {"source": name, "status": "error", "detail": message}
    finally:
        db.close()

    duration_ms = int((time.monotonic() - started) * 1000)
    _record(
        r,
        name,
        last_ok_at=datetime.now(timezone.utc).isoformat(),
        last_error="",
        state="ok",
        last_fetched=len(posts),
        last_new=len(inserted),
        last_duration_ms=duration_ms,
    )
    r.hincrby(_status_key(name), "total_new", len(inserted))
    logger.info("[intent] %s: fetched %d, saved %d new (%d ms)", name, len(posts), len(inserted), duration_ms)
    return {"source": name, "status": "ok", "fetched": len(posts), "new": len(inserted)}
