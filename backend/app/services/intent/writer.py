"""Reply drafts and one-line summaries for request posts.

Every post gets a template reply at once; posts worth it get a tailored
summary and reply from the local Ollama model when it's running.
"""

import json

import httpx

from app.core.config import settings

_TEMPLATES = {
    "WEBSITE_BUILD": (
        "Hi{name}, saw your post about {topic}. I build fast, mobile-first websites for small "
        "businesses, usually live within a week. Happy to send a couple of recent examples and a "
        "short plan for yours. Want me to?"
    ),
    "WEBSITE_FIX": (
        "Hi{name}, saw you need help with {topic}. I can look at the site today and send a short "
        "list of what's wrong and how I'd fix it, no charge for the review. Shall I?"
    ),
    "AUTOMATION": (
        "Hi{name}, re {topic}: I set up booking, WhatsApp and chat automations for small businesses "
        "so enquiries get answered even after hours. I can sketch how it'd work for you in a few "
        "lines. Interested?"
    ),
    "OTHER": (
        "Hi{name}, saw your post about {topic}. This is right up my street; I build websites and "
        "automations for small businesses. Happy to share examples and a quick plan. Want me to?"
    ),
}

_PROMPT = """You help a freelance web developer in India reply to people asking for work.
Read the post and answer strictly with JSON, no commentary:

{{"summary": string, "reply": string}}

- summary: one plain sentence (max 25 words) saying what they need and any budget or deadline.
- reply: a short, friendly first message (max 70 words) from the developer. Mention one specific
  detail from the post, propose a concrete next step, no buzzwords, no placeholders, no emojis.

Post title: {title}
Post text:
\"\"\"
{body}
\"\"\"
"""


def _topic(title: str) -> str:
    topic = title.strip().rstrip(".!?")
    for tag in ("[Hiring]", "[HIRING]", "[hiring]", "[Task]", "[TASK]", "[task]"):
        topic = topic.replace(tag, "")
    topic = topic.strip(" -:|")
    if len(topic) > 70:
        topic = topic[:67].rsplit(" ", 1)[0] + "…"
    return topic[:1].lower() + topic[1:] if topic else "your project"


def template_reply(fit: str, title: str, author: str | None = None) -> str:
    name = f" {author}" if author and len(author) <= 30 else " there"
    return _TEMPLATES.get(fit, _TEMPLATES["OTHER"]).format(name=name, topic=_topic(title))


def ollama_enrich(title: str, body: str) -> dict | None:
    """{"summary", "reply"} from the local model, or None when it's unavailable."""
    try:
        res = httpx.post(
            settings.OLLAMA_URL,
            json={
                "model": settings.OLLAMA_MODEL,
                "prompt": _PROMPT.format(title=title, body=body[:2500]),
                "format": "json",
                "stream": False,
            },
            timeout=settings.OLLAMA_TIMEOUT_S,
        )
        res.raise_for_status()
        parsed = json.loads(res.json()["response"])
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError):
        return None
    summary = str(parsed.get("summary") or "").strip()
    reply = str(parsed.get("reply") or "").strip()
    if not summary and not reply:
        return None
    return {"summary": summary or None, "reply": reply or None}
