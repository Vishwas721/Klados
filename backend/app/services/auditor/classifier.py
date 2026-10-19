"""Local LLM classification of website text via an Ollama-hosted model.

Ollama is a local dev dependency and isn't guaranteed to be running, so a
failed connection falls back to conservative defaults instead of raising -
callers shouldn't have to wrap every audit in a try/except just because the
model server is down.
"""

import json
from pathlib import Path
import sys

# Ensure backend root is on sys.path when executed directly as a script
_backend_root = str(Path(__file__).resolve().parents[3])
if _backend_root not in sys.path:
    sys.path.insert(0, _backend_root)

import httpx

OLLAMA_URL = "http://localhost:11434/api/generate"
OLLAMA_MODEL = "llama3:8b"
OLLAMA_TIMEOUT_S = 30.0

_PROMPT_TEMPLATE = """You are auditing a small business's website to find operational gaps \
that automation could fix. Read the website text below and answer strictly with JSON \
matching this schema, with no extra commentary:

{{
  "has_online_booking": boolean,
  "has_chat_widget": boolean,
  "operational_bottleneck": string
}}

- has_online_booking: true if visitors can book/schedule an appointment directly on the site.
- has_chat_widget: true if a live chat or chatbot widget is present.
- operational_bottleneck: a short phrase naming the biggest manual/operational gap you see \
(e.g. "no online booking, relies on phone calls").

Website text:
\"\"\"
{page_text}
\"\"\"
"""

_FALLBACK_RESULT = {
    "has_online_booking": False,
    "has_chat_widget": False,
    "operational_bottleneck": "unknown",
}


def query_ollama(page_text: str) -> dict:
    """Ask the local Ollama model to evaluate a website's operational gaps."""
    prompt = _PROMPT_TEMPLATE.format(page_text=page_text[:2000])

    try:
        response = httpx.post(
            OLLAMA_URL,
            json={
                "model": OLLAMA_MODEL,
                "prompt": prompt,
                "format": "json",
                "stream": False,
            },
            timeout=OLLAMA_TIMEOUT_S,
        )
        response.raise_for_status()
        parsed = json.loads(response.json()["response"])
    except (httpx.HTTPError, json.JSONDecodeError, KeyError, TypeError):
        return dict(_FALLBACK_RESULT)

    return {
        "has_online_booking": bool(parsed.get("has_online_booking", False)),
        "has_chat_widget": bool(parsed.get("has_chat_widget", False)),
        "operational_bottleneck": str(parsed.get("operational_bottleneck", "unknown")),
    }


if __name__ == "__main__":
    sample_text = (
        "Welcome to our clinic. Call us at (555) 123-4567 to book an appointment. "
        "We do not currently offer online booking or live chat support."
    )
    print(json.dumps(query_ollama(sample_text), indent=2))
