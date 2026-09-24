"""RQ worker: turns H3 cells into audited, persisted leads.

Runs as a separate process from the FastAPI app (`python -m app.worker`),
decoupling the slow discovery/audit/scrape pipeline from request handling.
"""

from datetime import datetime, timedelta, timezone
import logging
import os
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

QUEUE_NAME = "lead_tasks"

# Daily low-and-slow policy: cap leads per cell run, and pace audits with a
# delay so we don't hammer target sites back-to-back.
MAX_LEADS_PER_CELL = int(os.environ.get("MAX_LEADS_PER_CELL", "10"))
AUDIT_DELAY_MIN_S = int(os.environ.get("AUDIT_DELAY_MIN_S", "5"))
AUDIT_DELAY_MAX_S = int(os.environ.get("AUDIT_DELAY_MAX_S", "10"))

# Daily collection limit tracked via Redis
DAILY_LIMIT = int(os.environ.get("DAILY_LIMIT", "50"))
REDIS_DAILY_COUNTER_KEY = "leads_collected_today"

redis_conn = Redis.from_url(settings.REDIS_URL)


def get_leads_collected_today(r: Redis = redis_conn) -> int:
    """Return count of leads collected today from Redis."""
    try:
        val = r.get(REDIS_DAILY_COUNTER_KEY)
        return int(val) if val else 0
    except Exception as exc:
        logger.warning("[worker] Failed to get '%s' from Redis: %s", REDIS_DAILY_COUNTER_KEY, exc)
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
        logger.warning("[worker] Failed to increment '%s' in Redis: %s", REDIS_DAILY_COUNTER_KEY, exc)
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
    logger.info("[worker] === Starting process_h3_cell(hex_id='%s', query='%s', city='%s') ===", hex_id, query, city)

    # 1. Pre-check daily cap before scraping
    current_daily_count = get_leads_collected_today(redis_conn)
    logger.info("[worker] Daily leads collected today: %d / %d (limit)", current_daily_count, DAILY_LIMIT)
    if current_daily_count >= DAILY_LIMIT:
        logger.warning("[worker] Daily limit of %d reached. Sleeping until next cycle.", DAILY_LIMIT)
        return {
            "hex_id": hex_id,
            "query": query,
            "leads_processed": 0,
            "status": "daily_limit_reached",
        }

    # 2. Extract places from Google Maps
    lat, lng = cell_to_coords(hex_id)
    logger.info("[worker] Cell %s coordinates: lat=%.6f, lng=%.6f. Calling extract_places...", hex_id, lat, lng)
    raw_places = extract_places(query, lat, lng, limit=MAX_LEADS_PER_CELL, city=city)
    places = raw_places[:MAX_LEADS_PER_CELL]
    logger.info(
        "[worker] Raw places returned by extract_places: %d (capped to MAX_LEADS_PER_CELL=%d: %d)",
        len(raw_places),
        MAX_LEADS_PER_CELL,
        len(places),
    )

    if not places:
        logger.warning(
            "[worker] 0 raw places found on Google Maps for query '%s' at (%f, %f). Nothing to audit.",
            query,
            lat,
            lng,
        )
        return {
            "hex_id": hex_id,
            "query": query,
            "raw_places_found": 0,
            "leads_processed": 0,
            "status": "no_places_found",
        }

    # 3. Process and filter candidates
    db = SessionLocal()
    passed_validation = 0
    skipped_missing_name = 0
    skipped_missing_phone = 0
    skipped_duplicates = 0
    processed = 0

    try:
        for i, place in enumerate(places):
            candidate_idx = i + 1
            b_name = place.get("business_name")
            p_phone = place.get("phone_number")
            p_city = place.get("city") or city
            p_website = place.get("website_url")

            # Check daily limit before processing each lead
            daily_so_far = get_leads_collected_today(redis_conn)
            if daily_so_far >= DAILY_LIMIT:
                logger.warning(
                    "[worker] Daily limit of %d reached mid-batch at candidate %d/%d. Halting execution.",
                    DAILY_LIMIT,
                    candidate_idx,
                    len(places),
                )
                break

            # Validation check: business_name
            if not b_name:
                logger.warning(
                    "[worker] [Candidate %d/%d] DROPPED: Missing business_name. Raw data: %s",
                    candidate_idx,
                    len(places),
                    place,
                )
                skipped_missing_name += 1
                continue

            # Validation check: phone_number
            if not p_phone:
                logger.warning(
                    "[worker] [Candidate %d/%d] DROPPED: '%s' has NO phone number. (website=%s, place_url=%s)",
                    candidate_idx,
                    len(places),
                    b_name,
                    p_website,
                    place.get("place_url"),
                )
                skipped_missing_phone += 1
                continue

            passed_validation += 1
            logger.info(
                "[worker] [Candidate %d/%d] PASSED validation: '%s' (phone=%s, city='%s', website=%s)",
                candidate_idx,
                len(places),
                b_name,
                p_phone,
                p_city,
                p_website,
            )

            # Pre-Flight Deduplication Check in PostgreSQL
            if is_duplicate_lead(db, phone_number=p_phone, business_name=b_name, city=p_city):
                logger.info(
                    "[worker] [Candidate %d/%d] SKIPPED: Lead '%s' in '%s' (phone: %s) already exists in PostgreSQL.",
                    candidate_idx,
                    len(places),
                    b_name,
                    p_city,
                    p_phone,
                )
                skipped_duplicates += 1
                continue

            # Website audit
            logger.info(
                "[worker] [Candidate %d/%d] Starting website audit for '%s' (URL: %s)...",
                candidate_idx,
                len(places),
                b_name,
                p_website,
            )
            try:
                audit = audit_lead(p_website)
                logger.info(
                    "[worker] [Candidate %d/%d] Audit completed for '%s': category=%s, ssl=%s, mobile=%s, ttfb=%dms",
                    candidate_idx,
                    len(places),
                    b_name,
                    audit.get("category"),
                    audit.get("has_ssl"),
                    audit.get("is_mobile_responsive"),
                    audit.get("ttfb_ms", 0),
                )
            except Exception as exc:
                logger.error(
                    "[worker] [Candidate %d/%d] Audit exception for '%s' (%s): %s. Falling back to ghost profile.",
                    candidate_idx,
                    len(places),
                    b_name,
                    p_website,
                    exc,
                )
                audit = {
                    "category": "DIGITAL_GHOST" if not p_website else "LAGGY_UX",
                    "has_ssl": False,
                    "is_mobile_responsive": False,
                    "ttfb_ms": 0,
                    "dom_load_time_ms": 0,
                    "operational_bottleneck": f"Audit failed: {exc}",
                }

            # Upsert into PostgreSQL with explicit commit
            try:
                lead = _upsert_lead(db, place, hex_id, audit, city=p_city)
                db.commit()
                db.refresh(lead)
                new_today_count = increment_leads_collected_today(redis_conn)
                processed += 1
                logger.info(
                    "[worker] [Candidate %d/%d] EXPLICIT db.commit() SUCCESSFUL: Saved lead id=%s ('%s', %s, city='%s'). Total persisted today: %d/%d",
                    candidate_idx,
                    len(places),
                    lead.id,
                    b_name,
                    p_phone,
                    p_city,
                    new_today_count,
                    DAILY_LIMIT,
                )
            except Exception as db_exc:
                db.rollback()
                logger.error(
                    "[worker] [Candidate %d/%d] FAILED to commit lead '%s' to database: %s",
                    candidate_idx,
                    len(places),
                    b_name,
                    db_exc,
                )
                continue

            if i < len(places) - 1:
                delay = random.uniform(AUDIT_DELAY_MIN_S, AUDIT_DELAY_MAX_S)
                logger.info("[worker] Pacing: sleeping %.1fs before next lead...", delay)
                time.sleep(delay)
    finally:
        db.close()

    logger.info(
        "[worker] === Summary for cell %s ('%s'): raw_places=%d, passed_validation=%d, "
        "skipped_missing_phone=%d, skipped_duplicates=%d, saved_to_db=%d ===",
        hex_id,
        query,
        len(places),
        passed_validation,
        skipped_missing_phone,
        skipped_duplicates,
        processed,
    )

    return {
        "hex_id": hex_id,
        "query": query,
        "raw_places": len(places),
        "passed_validation": passed_validation,
        "skipped_missing_phone": skipped_missing_phone,
        "skipped_duplicates": skipped_duplicates,
        "leads_processed": processed,
    }


if __name__ == "__main__":
    from rq import Worker

    logger.info("Starting RQ worker on queue: %s", QUEUE_NAME)
    Worker([QUEUE_NAME], connection=redis_conn).work()
