"""Request radar: polls every request source on its interval.

Run as its own process (`python -m app.intent_poller`). It only makes plain
HTTP calls, so unlike the Maps worker it needs no browser or Xvfb.
"""

import logging
import time

from redis import Redis

from app.core.config import settings
from app.services.intent.poller import SOURCES, last_attempt_ts, poll_source, take_poll_request

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("intent_poller")

TICK_S = 10


def run_once(r: Redis, now: float | None = None) -> list[dict]:
    """Poll every source that's due or was asked for; return their results."""
    results = []
    for name, spec in SOURCES.items():
        forced = take_poll_request(r, name)
        current = now if now is not None else time.time()
        if forced or current - last_attempt_ts(r, name) >= spec.interval_s():
            try:
                results.append(poll_source(name, r))
            except Exception as exc:  # never let one source kill the loop
                logger.exception("[intent] %s crashed: %s", name, exc)
    return results


def main() -> None:
    r = Redis.from_url(settings.REDIS_URL)
    logger.info("Request radar started: %s", ", ".join(SOURCES))
    while True:
        try:
            run_once(r)
        except Exception as exc:  # Redis hiccup etc.
            logger.error("[intent] loop error: %s", exc)
        time.sleep(TICK_S)


if __name__ == "__main__":
    main()
