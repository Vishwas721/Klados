"""RQ worker: turns H3 cells into audited, persisted leads.

Runs as a separate process from the FastAPI app (`python -m app.worker`),
decoupling the slow discovery/audit/scrape pipeline from request handling.
"""

from datetime import datetime, timedelta, timezone
import logging
import random
import time

from redis import Redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Lead
from app.db.session import SessionLocal
from app.services.auditor.site_auditor import audit_lead
from app.services.discovery.geo_grid import cell_to_coords
from app.services.discovery.gmaps_extractor import extract_places, is_duplicate_lead

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

QUEUE_NAME = "lead_tasks"

# Daily low-and-slow policy: cap leads per cell run, and pace audits with a
# random delay so we don't hammer target sites back-to-back.
MAX_LEADS_PER_CELL = 10
AUDIT_DELAY_MIN_S = 30
AUDIT_DELAY_MAX_S = 60

# Daily collection limit tracked via Redis
DAILY_LIMIT = 50
REDIS_DAILY_COUNTER_KEY = "leads_collected_today"

redis_conn = Redis.from_url(settings.REDIS_URL)


def get_leads_collected_today(r: Redis = redis_conn) -> int:
    """Return count of leads collected today from Redis."""
    try:
        val = r.get(REDIS_DAILY_COUNTER_KEY)
        return int(val) if val else 0
    except Exception as exc:
        logger.warning("Failed to get '%s' from Redis: %s", REDIS_DAILY_COUNTER_KEY, exc)
        return 0


def increment_leads_collected_today(r: Redis = redis_conn) -> int:
    """Increment daily lead counter and ensure expiration at midnight UTC."""
    try:
        count = int(r.incr(REDIS_DAILY_COUNTER_KEY))
        if r.ttl(REDIS_DAILY_COUNTER_KEY) == -1:
            now = datetime.now(timezone.utc)
            tomorrow = (now + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            seconds_left = max(int((tomorrow - now).total_seconds()), 3600)
            r.expire(REDIS_DAILY_COUNTER_KEY, seconds_left)
        return count
    except Exception as exc:
        logger.warning("Failed to increment '%s' in Redis: %s", REDIS_DAILY_COUNTER_KEY, exc)
        return 0


def _upsert_lead(
    db: Session, place: dict, hex_id: str, audit: dict, city: str = "Bengaluru"
) -> Lead:
    lead = db.execute(
        select(Lead).where(
            Lead.phone_number == place["phone_number"],
            Lead.business_name == place["business_name"],
        )
    ).scalar_one_or_none()

    if lead is None:
        lead = Lead(
            business_name=place["business_name"],
            phone_number=place["phone_number"],
        )
        db.add(lead)

    lead.city = city
    lead.website_url = place.get("website_url")
    lead.latitude = place.get("latitude")
    lead.longitude = place.get("longitude")

    lead.category = audit.get("category", "DIGITAL_GHOST")
    lead.has_ssl = bool(audit.get("has_ssl", False))
    lead.is_mobile_responsive = bool(audit.get("is_mobile_responsive", False))
    lead.ttfb_ms = int(audit.get("ttfb_ms") or 0)
    lead.dom_load_time_ms = int(audit.get("dom_load_time_ms") or 0)
    lead.llm_audit_summary = audit.get("operational_bottleneck")

    if "has_chat_widget" in audit:
        lead.lacks_chat_widget = not audit["has_chat_widget"]
    if "has_online_booking" in audit:
        lead.lacks_booking_flow = not audit["has_online_booking"]

    # Provenance: where this lead came from and where in the grid it lives.
    lead.origin_source_url = place.get("origin_source_url", "")
    lead.h3_hex_id = hex_id

    lead.status = "AUDITED"
    return lead


def process_h3_cell(hex_id: str, query: str, city: str = "Bengaluru") -> dict:
    """Discover businesses in an H3 cell, audit each site, and upsert leads."""
    # Pre-check daily cap before scraping
    current_daily_count = get_leads_collected_today(redis_conn)
    if current_daily_count >= DAILY_LIMIT:
        logger.warning("Daily limit of 50 reached. Sleeping until next cycle.")
        return {
            "hex_id": hex_id,
            "query": query,
            "leads_processed": 0,
            "status": "daily_limit_reached",
        }

    lat, lng = cell_to_coords(hex_id)
    places = extract_places(query, lat, lng, limit=MAX_LEADS_PER_CELL, city=city)[:MAX_LEADS_PER_CELL]

    db = SessionLocal()
    processed = 0
    try:
        for i, place in enumerate(places):
            # Enforce daily limit check before each lead audit
            if get_leads_collected_today(redis_conn) >= DAILY_LIMIT:
                logger.warning("Daily limit of 50 reached. Sleeping until next cycle.")
                break

            b_name = place.get("business_name")
            p_phone = place.get("phone_number")
            p_city = place.get("city") or city

            if not b_name or not p_phone:
                # Can't dedupe or persist a lead we can't identify.
                continue

            # Pre-Flight Check: if phone or (name, city) exists in PostgreSQL, skip audit completely
            if is_duplicate_lead(db, phone_number=p_phone, business_name=b_name, city=p_city):
                logger.info(
                    "Lead '%s' in '%s' (phone: %s) already exists. Skipping audit.",
                    b_name,
                    p_city,
                    p_phone,
                )
                continue

            # Safe website audit with error handling
            try:
                audit = audit_lead(place.get("website_url"))
            except Exception as exc:
                logger.error(
                    "Audit error for %s (%s): %s. Falling back to ghost profile.",
                    b_name,
                    place.get("website_url"),
                    exc,
                )
                audit = {
                    "category": "DIGITAL_GHOST" if not place.get("website_url") else "LAGGY_UX",
                    "has_ssl": False,
                    "is_mobile_responsive": False,
                    "ttfb_ms": 0,
                    "dom_load_time_ms": 0,
                    "operational_bottleneck": f"Audit failed: {exc}",
                }

            try:
                _upsert_lead(db, place, hex_id, audit, city=p_city)
                db.commit()
                increment_leads_collected_today(redis_conn)
                processed += 1
            except Exception as db_exc:
                db.rollback()
                logger.error("Failed to commit lead '%s' to database: %s", b_name, db_exc)
                continue

            if i < len(places) - 1:
                time.sleep(random.uniform(AUDIT_DELAY_MIN_S, AUDIT_DELAY_MAX_S))
    finally:
        db.close()

    return {"hex_id": hex_id, "query": query, "leads_processed": processed}


if __name__ == "__main__":
    from rq import Worker

    logger.info("Starting RQ worker on queue: %s", QUEUE_NAME)
    Worker([QUEUE_NAME], connection=redis_conn).work()
