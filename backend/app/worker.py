"""RQ worker: turns H3 cells into audited, persisted leads.

Runs as a separate process from the FastAPI app (`python -m app.worker`),
decoupling the slow discovery/audit/scrape pipeline from request handling.
"""

from datetime import datetime, timedelta, timezone
import logging
import random
import time
import uuid

import h3
from redis import Redis
from rq import Queue
from rq.timeouts import JobTimeoutException
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.lookups import clear_stale_exhaustion, find_campaign, find_search_history
from app.db.models import CampaignTracker, Lead, SearchHistory
from app.db.session import SessionLocal
from app.services.auditor.site_auditor import SiteAuditor
from app.services.discovery.coverage import MAPS_BLOCKED_KEY, mark_seen, unmark_seen, unseen_cells
from app.services.discovery.geo_grid import cell_to_coords
from app.services.discovery.gmaps_extractor import MapsBlockedError, extract_places, is_duplicate_lead
from app.services.discovery.targets import get_next_search_target

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

QUEUE_NAME = settings.QUEUE_NAME
JOB_TIMEOUT_S = 3600

MAX_LEADS_PER_CELL = settings.MAX_LEADS_PER_CELL
AUDIT_DELAY_MIN_S = settings.AUDIT_DELAY_MIN_S
AUDIT_DELAY_MAX_S = settings.AUDIT_DELAY_MAX_S

# Daily collection limit tracked via Redis
DAILY_LIMIT = settings.DAILY_LIMIT
REDIS_DAILY_COUNTER_KEY = "leads_collected_today"

# Set while Google is blocking us; every job backs off until it expires
REDIS_MAPS_BLOCKED_KEY = MAPS_BLOCKED_KEY

# A cell yielding fewer new leads than this spills over into its neighbours
EXPANSION_THRESHOLD = 10
MAX_EXPANSION_DEPTH = 2
MAX_NEIGHBOURS_PER_EXPANSION = 2

# Cells queued when the worker jumps to a fresh (city, niche) target
MACRO_EXPANSION_CELLS = 6

redis_conn = Redis.from_url(settings.REDIS_URL)


def get_leads_collected_today(r: Redis = redis_conn) -> int:
    """Return count of leads collected today from Redis.

    Fails closed: if Redis can't be read, report the limit as reached rather
    than letting the worker scrape without a cap.
    """
    try:
        val = r.get(REDIS_DAILY_COUNTER_KEY)
        return int(val) if val else 0
    except Exception as exc:
        logger.error(
            "[worker] Failed to read '%s' from Redis (%s); treating daily limit as reached.",
            REDIS_DAILY_COUNTER_KEY,
            exc,
        )
        return DAILY_LIMIT


def increment_leads_collected_today(r: Redis = redis_conn) -> int:
    """Increment daily lead counter and ensure expiration at midnight UTC."""
    count = int(r.incr(REDIS_DAILY_COUNTER_KEY))
    if r.ttl(REDIS_DAILY_COUNTER_KEY) == -1:
        now = datetime.now(timezone.utc)
        tomorrow = (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        r.expire(REDIS_DAILY_COUNTER_KEY, max(int((tomorrow - now).total_seconds()), 1))
    return count


def _maps_blocked_reason(r: Redis = redis_conn) -> str | None:
    try:
        val = r.get(REDIS_MAPS_BLOCKED_KEY)
    except Exception:
        return None
    return val.decode() if isinstance(val, bytes) else val


def _back_off_blocked_cell(hex_id: str, query: str, city: str, reason: str) -> dict:
    """Release the cell for a later run and record the run as blocked."""
    unmark_seen(redis_conn, city, query, hex_id)
    db = SessionLocal()
    try:
        _update_search_history(db, query, city, 0, status="BLOCKED")
    finally:
        db.close()
    return {"hex_id": hex_id, "query": query, "leads_processed": 0, "status": "maps_blocked", "reason": reason}


def get_neighboring_cells(hex_id: str, k: int = 1) -> set[str]:
    """Return the cells exactly k steps away from hex_id."""
    return set(h3.grid_ring(hex_id, k))


def _insert_lead_on_conflict_do_nothing(
    db: Session, place: dict, hex_id: str, audit: dict, city: str = "Bengaluru"
) -> uuid.UUID | None:
    """Insert lead into PostgreSQL with ON CONFLICT DO NOTHING.

    Untargeted, so a clash on either the place_id index or
    uq_leads_phone_business is skipped instead of raising.
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

    stmt = pg_insert(Lead).values(**values).on_conflict_do_nothing().returning(Lead.id)
    return db.execute(stmt).scalar_one_or_none()


def _update_search_history(
    db: Session, niche: str, city: str, leads_added: int, status: str = "COMPLETED"
) -> None:
    """Update or initialize search_history entry in PostgreSQL."""
    try:
        rec = find_search_history(db, city, niche)

        if rec is None:
            rec = SearchHistory(
                niche=niche.strip(),
                city=city.strip(),
                leads_count=leads_added,
                status=status,
            )
            db.add(rec)
        else:
            rec.leads_count += leads_added
            rec.last_run_at = datetime.now(timezone.utc)
            rec.status = status
        db.commit()
    except Exception as exc:
        db.rollback()
        logger.warning("[worker] Failed to update search_history for '%s' in '%s': %s", niche, city, exc)


def _fallback_audit(website_url: str | None, exc: Exception) -> dict:
    return {
        "category": "DIGITAL_GHOST" if not website_url else "LAGGY_UX",
        "has_ssl": False,
        "is_mobile_responsive": False,
        "ttfb_ms": 0,
        "dom_load_time_ms": 0,
        "operational_bottleneck": f"Audit failed: {str(exc).splitlines()[0][:200]}",
    }


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
        logger.warning(
            "[worker] Daily limit of %d reached. Releasing cell %s for a later run.", DAILY_LIMIT, hex_id
        )
        unmark_seen(redis_conn, city, query, hex_id)
        return {
            "hex_id": hex_id,
            "query": query,
            "leads_processed": 0,
            "status": "daily_limit_reached",
        }

    blocked_reason = _maps_blocked_reason(redis_conn)
    if blocked_reason:
        logger.warning(
            "[worker] Maps cooldown active (%s). Releasing cell %s without scraping.", blocked_reason, hex_id
        )
        return _back_off_blocked_cell(hex_id, query, city, blocked_reason)

    # 2. Extract places from Google Maps (safe IP limit: capped at MAX_LEADS_PER_CELL)
    lat, lng = cell_to_coords(hex_id)
    logger.info("[worker] Cell %s coordinates: lat=%.6f, lng=%.6f. Calling extract_places...", hex_id, lat, lng)
    try:
        raw_places = extract_places(query, lat, lng, limit=MAX_LEADS_PER_CELL, city=city)
    except JobTimeoutException:
        raise
    except MapsBlockedError as exc:
        logger.error(
            "[worker] Google blocked the Maps search (%s). Pausing all scraping for %ds.",
            exc,
            settings.MAPS_BLOCK_COOLDOWN_S,
        )
        redis_conn.set(REDIS_MAPS_BLOCKED_KEY, str(exc), ex=settings.MAPS_BLOCK_COOLDOWN_S)
        return _back_off_blocked_cell(hex_id, query, city, str(exc))
    except Exception as exc:
        logger.error("[worker] extract_places failed for cell %s: %s", hex_id, exc)
        raw_places = []
    places = raw_places[:MAX_LEADS_PER_CELL]
    logger.info(
        "[worker] Raw places returned by extract_places: %d (capped to MAX_LEADS_PER_CELL=%d: %d)",
        len(raw_places),
        MAX_LEADS_PER_CELL,
        len(places),
    )

    db = SessionLocal()
    # One browser for every audit in this cell, launched on first use
    auditor = SiteAuditor()
    passed_validation = 0
    skipped_missing_name = 0
    skipped_missing_phone = 0
    skipped_duplicates = 0
    processed = 0
    hit_daily_limit = False

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
                hit_daily_limit = True
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
                audit = auditor.audit(p_website)
                logger.info(
                    "[worker] [Candidate %d/%d] Audit completed for '%s': category=%s, ssl=%s, mobile=%s, ttfb=%sms, tech=%s",
                    candidate_idx,
                    len(places),
                    b_name,
                    audit.get("category"),
                    audit.get("has_ssl"),
                    audit.get("is_mobile_responsive"),
                    audit.get("ttfb_ms"),
                    audit.get("detected_tech"),
                )
            except JobTimeoutException:
                raise
            except Exception as exc:
                logger.error(
                    "[worker] [Candidate %d/%d] Audit exception for '%s' (%s): %s. Using fallback profile.",
                    candidate_idx,
                    len(places),
                    b_name,
                    p_website,
                    exc,
                )
                audit = _fallback_audit(p_website, exc)

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

        # Always record the run so the search doesn't stay RUNNING forever
        _update_search_history(db, query, city, processed)

    finally:
        auditor.close()
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

    expanded_cells = []
    if hit_daily_limit:
        # The rest of this cell was never looked at: let a later run redo it,
        # and don't burn neighbouring cells on jobs that would just bail out.
        unmark_seen(redis_conn, city, query, hex_id)
    else:
        expanded_cells = _expand_coverage(hex_id, query, city, expansion_depth, processed)

    return {
        "hex_id": hex_id,
        "query": query,
        "raw_places": len(places),
        "passed_validation": passed_validation,
        "skipped_missing_phone": skipped_missing_phone,
        "skipped_duplicates": skipped_duplicates,
        "leads_processed": processed,
        "expanded_cells": expanded_cells,
        "status": "daily_limit_reached" if hit_daily_limit else "completed",
    }


def _expand_coverage(
    hex_id: str, query: str, city: str, expansion_depth: int, processed: int
) -> list[str]:
    """Smart Spatial Expansion, then exhaustion handling.

    A cell yielding < EXPANSION_THRESHOLD new leads spills into up to
    MAX_NEIGHBOURS_PER_EXPANSION unscanned neighbours inside the city grid.
    Only once every cell of the city has been scanned is the (city, niche)
    pair marked exhausted and the worker moved on to a fresh target.
    """
    try:
        remaining = unseen_cells(redis_conn, city, query)
    except ValueError:
        # City has no bounding box (e.g. a macro target alias removed later)
        return []

    expanded_cells = []
    if processed < EXPANSION_THRESHOLD and expansion_depth < MAX_EXPANSION_DEPTH:
        remaining_set = set(remaining)
        neighbours = sorted(c for c in get_neighboring_cells(hex_id, k=1) if c in remaining_set)
        to_queue = neighbours[:MAX_NEIGHBOURS_PER_EXPANSION]
        if to_queue:
            mark_seen(redis_conn, city, query, to_queue)
            task_queue = Queue(QUEUE_NAME, connection=redis_conn)
            for next_cell in to_queue:
                task_queue.enqueue(
                    process_h3_cell,
                    args=(next_cell, query, city, expansion_depth + 1),
                    job_timeout=JOB_TIMEOUT_S,
                )
                expanded_cells.append(next_cell)
            logger.info(
                "[worker] Smart Spatial Expansion: found %d (< %d) new leads in cell %s. "
                "Expanding outward into %d adjacent cell(s) at depth %d: %s",
                processed,
                EXPANSION_THRESHOLD,
                hex_id,
                len(expanded_cells),
                expansion_depth + 1,
                expanded_cells,
            )
            remaining = [c for c in remaining if c not in set(to_queue)]

    if not remaining:
        _handle_exhaustion(query, city)

    return expanded_cells


def _handle_exhaustion(query: str, city: str) -> None:
    """Record a fully covered (city, niche) pair and macro-expand to a fresh target."""
    db = SessionLocal()
    try:
        norm_city = city.strip()
        norm_niche = query.strip()
        now = datetime.now(timezone.utc)

        tracker = find_campaign(db, norm_city, norm_niche)

        if not tracker:
            db.add(CampaignTracker(city=norm_city, niche=norm_niche, is_exhausted=True, last_scraped_at=now))
        else:
            tracker.is_exhausted = True
            tracker.last_scraped_at = now
        db.commit()
        logger.info("[worker] Campaign exhausted: every cell of '%s' scanned for '%s'.", norm_city, norm_niche)

        if get_leads_collected_today(redis_conn) >= DAILY_LIMIT:
            return

        clear_stale_exhaustion(db)
        task_queue = Queue(QUEUE_NAME, connection=redis_conn)
        for _ in range(50):
            new_city, new_niche = get_next_search_target("random")
            candidate = find_campaign(db, new_city, new_niche)
            if candidate and candidate.is_exhausted:
                continue

            try:
                cells = unseen_cells(redis_conn, new_city, new_niche)[:MACRO_EXPANSION_CELLS]
            except ValueError:
                continue
            if not cells:
                continue

            mark_seen(redis_conn, new_city, new_niche, cells)
            for c in cells:
                task_queue.enqueue(process_h3_cell, args=(c, new_niche, new_city, 0), job_timeout=JOB_TIMEOUT_S)
            logger.info("[worker] Macro Expansion: Jumped to %s - %s", new_city, new_niche)
            break
    except Exception as exc:
        db.rollback()
        logger.error("[worker] Failed macro expansion: %s", exc)
    finally:
        db.close()


if __name__ == "__main__":
    from rq import Worker

    logger.info("Starting RQ worker on queue: %s", QUEUE_NAME)
    Worker([QUEUE_NAME], connection=redis_conn).work()
