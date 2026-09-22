"""RQ worker: turns H3 cells into audited, persisted leads.

Runs as a separate process from the FastAPI app (`python -m app.worker`),
decoupling the slow discovery/audit/scrape pipeline from request handling.
"""

import random
import time

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Lead
from app.db.session import SessionLocal
from app.services.auditor.site_auditor import audit_lead
from app.services.discovery.geo_grid import cell_to_coords
from app.services.discovery.gmaps_extractor import extract_places

QUEUE_NAME = "lead_tasks"

# Daily low-and-slow policy: cap leads per cell run, and pace audits with a
# random delay so we don't hammer target sites back-to-back.
MAX_LEADS_PER_CELL = 10
AUDIT_DELAY_MIN_S = 30
AUDIT_DELAY_MAX_S = 60


def _upsert_lead(db: Session, place: dict, hex_id: str, audit: dict) -> Lead:
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
    lead.origin_source_url = place["origin_source_url"]
    lead.h3_hex_id = hex_id

    lead.status = "AUDITED"
    return lead


def process_h3_cell(hex_id: str, query: str) -> dict:
    """Discover businesses in an H3 cell, audit each site, and upsert leads."""
    lat, lng = cell_to_coords(hex_id)
    places = extract_places(query, lat, lng, limit=MAX_LEADS_PER_CELL)[:MAX_LEADS_PER_CELL]

    db = SessionLocal()
    processed = 0
    try:
        for i, place in enumerate(places):
            if not place.get("business_name") or not place.get("phone_number"):
                # Can't dedupe or persist a lead we can't identify.
                continue

            audit = audit_lead(place.get("website_url"))
            _upsert_lead(db, place, hex_id, audit)
            db.commit()
            processed += 1

            if i < len(places) - 1:
                time.sleep(random.uniform(AUDIT_DELAY_MIN_S, AUDIT_DELAY_MAX_S))
    finally:
        db.close()

    return {"hex_id": hex_id, "query": query, "leads_processed": processed}


if __name__ == "__main__":
    from redis import Redis
    from rq import Worker

    from app.core.config import settings

    redis_conn = Redis.from_url(settings.REDIS_URL)
    Worker([QUEUE_NAME], connection=redis_conn).work()
