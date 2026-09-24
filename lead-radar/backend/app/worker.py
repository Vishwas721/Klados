"""RQ worker: turns H3 cells into audited, persisted leads.

Runs as a separate process from the FastAPI app (`python -m app.worker`),
decoupling the slow discovery/audit/scrape pipeline from request handling.
"""

from datetime import datetime, timedelta, timezone
import logging
import os
import random
import time
import uuid

import h3
from redis import Redis
from rq import Queue
from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Lead, SearchHistory
from app.db.session import SessionLocal
from app.services.auditor.site_auditor import audit_lead
from app.services.discovery.geo_grid import cell_to_coords
from app.services.discovery.gmaps_extractor import extract_places, is_duplicate_lead

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

QUEUE_NAME = "lead_tasks"

# Safe IP limits: cap leads per cell to 20, and pace audits with a delay
MAX_LEADS_PER_CELL = int(os.environ.get("MAX_LEADS_PER_CELL", "20"))
AUDIT_DELAY_MIN_S = int(os.environ.get("AUDIT_DELAY_MIN_S", "3"))
AUDIT_DELAY_MAX_S = int(os.environ.get("AUDIT_DELAY_MAX_S", "7"))

# Daily collection limit tracked via Redis
DAILY_LIMIT = int(os.environ.get("DAILY_LIMIT", "50"))
REDIS_DAILY_COUNTER_KEY = "leads_collected_today"

# Maximum recursive expansion depth for spatial ring expansion
MAX_EXPANSION_DEPTH = 2

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


def get_neighboring_cells(hex_id: str, k: int = 1) -> set[str]:
    """Return neighboring cells at distance k using h3 k_ring / grid_disk."""
    if hasattr(h3, "grid_ring"):
        return set(h3.grid_ring(hex_id, k))
    elif hasattr(h3, "k_ring"):
        cells = set(h3.k_ring(hex_id, k))
        cells.discard(hex_id)
        return cells
    elif hasattr(h3, "grid_disk"):
        cells = set(h3.grid_disk(hex_id, k))
        cells.discard(hex_id)
        return cells
    return set()


def _insert_lead_on_conflict_do_nothing(
    db: Session, place: dict, hex_id: str, audit: dict, city: str = "Bengaluru"
) -> uuid.UUID | None:
    """Insert lead into PostgreSQL with ON CONFLICT DO NOTHING.

    Uses place_id unique index if available, falling back to uq_leads_phone_business.
    Returns the created Lead UUID, or None if the record already existed.
    """
    values = {
        "business_name": place["business_name"],
        "phone_number": place["phone_number"],
        "place_id": place.get("place_id"),
        "website_url": place.get("website_url"),
        "city": city,
        "latitude": place.get("latitude"),
        "longitude": place.get("longitude"),
        "category": audit.get("category", "DIGITAL_GHOST"),
        "has_ssl": bool(audit.get("has_ssl", False)),
        "is_mobile_responsive": bool(audit.get("is_mobile_responsive", False)),
        "ttfb_ms": int(audit.get("ttfb_ms") or 0),
        "dom_load_time_ms": int(audit.get("dom_load_time_ms") or 0),
        "detected_tech": audit.get("detected_tech", []),
        "llm_audit_summary": audit.get("operational_bottleneck"),
        "lacks_chat_widget": not audit["has_chat_widget"] if "has_chat_widget" in audit else None,
        "lacks_booking_flow": not audit["has_online_booking"] if "has_online_booking" in audit else None,
        "origin_source_url": place.get("origin_source_url", ""),
        "h3_hex_id": hex_id,
        "status": "AUDITED",
    }

    if place.get("place_id"):
        stmt = (
            pg_insert(Lead)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["place_id"])
            .returning(Lead.id)
        )
    else:
        stmt = (
            pg_insert(Lead)
            .values(**values)
            .on_conflict_do_nothing(constraint="uq_leads_phone_business")
            .returning(Lead.id)
        )

    res = db.execute(stmt)
    return res.scalar_one_or_none()


def _update_search_history(db: Session, niche: str, city: str, leads_added: int) -> None:
    """Update or initialize search_history entry in PostgreSQL."""
    try:
        norm_niche = niche.strip().lower()
        norm_city = city.strip().lower()
        rec = db.execute(
            select(SearchHistory).where(
                func.lower(SearchHistory.niche) == norm_niche,
                func.lower(SearchHistory.city) == norm_city,
            )
        ).scalar_one_or_none()

        if rec is None:
            rec = SearchHistory(
                niche=niche.strip(),
                city=city.strip(),
                leads_count=leads_added,
                status="COMPLETED",
            )
            db.add(rec)
        else:
            rec.leads_count += leads_added
            rec.last_run_at = datetime.now(timezone.utc)
            rec.status = "COMPLETED"
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("[worker] Failed to update search_history for '%s' in '%s': %s", niche, city, exc)


def process_h3_cell(
    hex_id: str, query: str, city: str = "Bengaluru", expansion_depth: int = 0
) -> dict:
    """Discover businesses in an H3 cell, audit each site, and upsert leads with ON CONFLICT DO NOTHING."""
    logger.info(
        "[worker] === Starting process_h3_cell(hex_id='%s', query='%s', city='%s', depth=%d) ===",
        hex_id,
        query,
        city,
        expansion_depth,
    )

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

    # 2. Extract places from Google Maps (safe IP limit: capped at MAX_LEADS_PER_CELL=20)
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
            p_place_id = place.get("place_id")

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
                "[worker] [Candidate %d/%d] PASSED validation: '%s' (phone=%s, place_id=%s, city='%s', website=%s)",
                candidate_idx,
                len(places),
                b_name,
                p_phone,
                p_place_id,
                p_city,
                p_website,
            )

            # Pre-Flight Deduplication Check in PostgreSQL
            if is_duplicate_lead(
                db, phone_number=p_phone, business_name=b_name, city=p_city, place_id=p_place_id
            ):
                logger.info(
                    "[worker] [Candidate %d/%d] SKIPPED: Lead '%s' in '%s' (phone: %s, place_id: %s) already exists in PostgreSQL.",
                    candidate_idx,
                    len(places),
                    b_name,
                    p_city,
                    p_phone,
                    p_place_id,
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

            # Upsert into PostgreSQL with ON CONFLICT DO NOTHING
            try:
                inserted_id = _insert_lead_on_conflict_do_nothing(
                    db, place, hex_id, audit, city=p_city
                )
                db.commit()

                if inserted_id is not None:
                    new_today_count = increment_leads_collected_today(redis_conn)
                    processed += 1
                    logger.info(
                        "[worker] [Candidate %d/%d] EXPLICIT db.commit() SUCCESSFUL: Saved lead id=%s ('%s', %s, city='%s'). Total persisted today: %d/%d",
                        candidate_idx,
                        len(places),
                        inserted_id,
                        b_name,
                        p_phone,
                        p_city,
                        new_today_count,
                        DAILY_LIMIT,
                    )
                else:
                    logger.info(
                        "[worker] [Candidate %d/%d] ON CONFLICT DO NOTHING triggered: '%s' overlapping cell data ignored cleanly.",
                        candidate_idx,
                        len(places),
                        b_name,
                    )
                    skipped_duplicates += 1
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

        # Update search_history with newly found leads
        if processed > 0:
            _update_search_history(db, query, city, processed)

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

    # 4. Smart Spatial Expansion (Fallback):
    # If the worker finds < 10 new leads in this cell, automatically expand outward into
    # adjacent neighborhood cells using h3 k_ring/grid_disk, queuing unvisited cells.
    expanded_cells = []
    if processed < 10 and expansion_depth < MAX_EXPANSION_DEPTH:
        seen_cells_key = f"seen_cells:{city.strip().lower()}:{query.strip().lower()}"
        redis_conn.sadd(seen_cells_key, hex_id)

        neighbors = get_neighboring_cells(hex_id, k=1)
        unvisited = [c for c in sorted(neighbors) if not redis_conn.sismember(seen_cells_key, c)]
        # Queue up to 2 unvisited adjacent cells for gradual expansion
        to_queue = unvisited[:2]

        if to_queue:
            task_queue = Queue(QUEUE_NAME, connection=redis_conn)
            for next_cell in to_queue:
                redis_conn.sadd(seen_cells_key, next_cell)
                task_queue.enqueue(
                    process_h3_cell, next_cell, query, city, expansion_depth + 1
                )
                expanded_cells.append(next_cell)
            logger.info(
                "[worker] Smart Spatial Expansion: found %d (< 10) new leads in cell %s. "
                "Expanding outward into %d adjacent cell(s) at depth %d: %s",
                processed,
                hex_id,
                len(expanded_cells),
                expansion_depth + 1,
                expanded_cells,
            )

    return {
        "hex_id": hex_id,
        "query": query,
        "raw_places": len(places),
        "passed_validation": passed_validation,
        "skipped_missing_phone": skipped_missing_phone,
        "skipped_duplicates": skipped_duplicates,
        "leads_processed": processed,
        "expanded_cells": expanded_cells,
    }


if __name__ == "__main__":
    from rq import Worker

    logger.info("Starting RQ worker on queue: %s", QUEUE_NAME)
    Worker([QUEUE_NAME], connection=redis_conn).work()
