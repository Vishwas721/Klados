"""Instant Telegram alerts for hot request posts (optional, free).

Create a bot with @BotFather, message it once, then set TELEGRAM_BOT_TOKEN
and TELEGRAM_CHAT_ID. Without both, alerts are skipped.
"""

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

FIT_LABELS = {
    "WEBSITE_BUILD": "New website",
    "WEBSITE_FIX": "Website fix",
    "AUTOMATION": "Automation",
    "OTHER": "Other",
}


def alerts_enabled() -> bool:
    return bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID)


def format_alert(post) -> str:
    budget = f" · ~${post.budget_usd:,.0f}" if post.budget_usd else ""
    lines = [
        f"🔥 {post.score}/100 · {FIT_LABELS.get(post.fit, post.fit)} · {post.source}{budget}",
        post.title,
    ]
    if post.summary:
        lines.append(post.summary)
    lines.append(post.url)
    return "\n".join(lines)


def send_alert(post) -> bool:
    if not alerts_enabled():
        return False
    try:
        res = httpx.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={
                "chat_id": settings.TELEGRAM_CHAT_ID,
                "text": format_alert(post),
                "disable_web_page_preview": True,
            },
            timeout=10.0,
        )
        res.raise_for_status()
        return True
    except httpx.HTTPError as exc:
        logger.warning("[intent] Telegram alert failed: %s", exc)
        return False
