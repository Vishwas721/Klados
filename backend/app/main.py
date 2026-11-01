from datetime import datetime, timezone
from typing import Literal
import uuid

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from redis import Redis
from rq import Queue
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.lookups import clear_stale_exhaustion, find_campaign, find_search_history
from app.db.models import CampaignTracker, Lead, SearchHistory
from app.db.session import get_db
from app.services.discovery.coverage import MAPS_BLOCKED_KEY, mark_seen, unseen_cells
from app.services.discovery.targets import BUSINESS_NICHES, CITY_BOUNDING_BOXES

app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

redis_conn = Redis.from_url(settings.REDIS_URL)
task_queue = Queue(settings.QUEUE_NAME, connection=redis_conn)

# Enqueued by dotted path so the API process never imports the browser stack
PROCESS_CELL_TASK = "app.worker.process_h3_cell"
JOB_TIMEOUT_S = 3600
MAX_CELLS_PER_SCAN = 6

LeadCategory = Literal[
    "DIGITAL_GHOST",
    "DIGITAL_DINOSAUR",
    "LAGGY_UX",
    "AUTOMATION_CANDIDATE",
]

OutreachStatus = Literal[
    "PENDING",
    "AUDITED",
    "CONTACTED_WHATSAPP",
    "CONTACTED_EMAIL",
    "RESPONDED",
    "CONVERTED",
    "OPTED_OUT",
]


class ScrapeTriggerRequest(BaseModel):
    query: str = Field(min_length=1, max_length=255)
    city: str = Field(min_length=1, max_length=100)
    max_cells: int = Field(default=MAX_CELLS_PER_SCAN, le=MAX_CELLS_PER_SCAN, ge=1)


class ScrapeTriggerResponse(BaseModel):
    task_ids: list[str]
    cells_queued: int
    cells_remaining: int


class SearchHistoryOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    niche: str
    city: str
    last_run_at: datetime
    leads_count: int
    status: str
    is_locked: bool
    locked_until: datetime


class ExhaustedCampaignOut(BaseModel):
    city: str
    niche: str
    last_scraped_at: datetime


class LeadStatusUpdate(BaseModel):
    status: OutreachStatus


class LeadStatsOut(BaseModel):
    total: int
    by_category: dict[str, int]
    opted_out: int


class TargetsOut(BaseModel):
    cities: list[str]
    niches: list[str]


class LeadOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    place_id: str | None = None
    business_name: str
    phone_number: str
    email: str | None
    website_url: str | None
    city: str
    h3_hex_id: str | None
    latitude: float | None
    longitude: float | None
    category: str
    has_ssl: bool
    is_mobile_responsive: bool
    ttfb_ms: int
    dom_load_time_ms: int
    detected_tech: list
    llm_audit_summary: str | None
    lacks_chat_widget: bool | None
    lacks_booking_flow: bool | None
    origin_source_url: str
    opted_out: bool
    status: str


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/api/scrape/trigger", response_model=ScrapeTriggerResponse)
def trigger_scrape(payload: ScrapeTriggerRequest, db: Session = Depends(get_db)):
    # 1. Daily Execution Lock Check (24-hour lock per niche + city, matched
    # on canonical keys so "Gyms" and "gym" share one lock)
    history = find_search_history(db, payload.city, payload.query)

    if history and history.is_locked:
        unlock_time = history.locked_until
        now = datetime.now(timezone.utc)
        remaining_s = max(0, int((unlock_time - now).total_seconds()))
        rem_h = remaining_s // 3600
        rem_m = (remaining_s % 3600) // 60
        unlock_str = unlock_time.strftime("%b %d, %I:%M %p UTC")
        raise HTTPException(
            status_code=429,
            detail=(
                f"Daily limit reached for '{payload.query}' in '{payload.city}'. "
                f"Locked until {unlock_str} ({rem_h}h {rem_m}m remaining). Check back tomorrow."
            ),
            headers={"Retry-After": str(remaining_s)},
        )

    # 2. Don't queue work while Google is blocking Maps searches
    blocked_ttl = redis_conn.ttl(MAPS_BLOCKED_KEY)
    if blocked_ttl and blocked_ttl > 0:
        raise HTTPException(
            status_code=503,
            detail=(
                "Google is temporarily blocking Maps searches. Scanning is paused for "
                f"another {max(1, blocked_ttl // 60)} min to protect the IP."
            ),
            headers={"Retry-After": str(blocked_ttl)},
        )

    # 3. Pick the next not-yet-scanned cells, nearest the city centre first,
    # so each run covers new ground instead of re-scraping the same cells.
    try:
        candidates = unseen_cells(redis_conn, payload.city, payload.query)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    if not candidates:
        raise HTTPException(
            status_code=409,
            detail=(
                f"Every area of '{payload.city}' has already been scanned for "
                f"'{payload.query}' recently. Try a different city or niche."
            ),
        )

    # Unscanned cells again (the coverage record expired): no longer exhausted
    tracker = find_campaign(db, payload.city, payload.query)
    if tracker and tracker.is_exhausted:
        tracker.is_exhausted = False

    selected_cells = candidates[: payload.max_cells]
    mark_seen(redis_conn, payload.city, payload.query, selected_cells)

    # 4. Update or create SearchHistory lock
    if history is None:
        history = SearchHistory(
            niche=payload.query.strip(),
            city=payload.city.strip(),
            status="RUNNING",
            last_run_at=datetime.now(timezone.utc),
        )
        db.add(history)
    else:
        history.status = "RUNNING"
        history.last_run_at = datetime.now(timezone.utc)
    db.commit()

    # 5. Enqueue initial H3 cells to RQ
    jobs = [
        task_queue.enqueue(
            PROCESS_CELL_TASK, args=(hex_id, payload.query, payload.city, 0), job_timeout=JOB_TIMEOUT_S
        )
        for hex_id in selected_cells
    ]

    return ScrapeTriggerResponse(
        task_ids=[job.id for job in jobs],
        cells_queued=len(jobs),
        cells_remaining=len(candidates) - len(selected_cells),
    )


@app.get("/api/targets", response_model=TargetsOut)
def get_targets():
    """Cities with a configured grid and suggested niches, for the scan form."""
    cities = [key.replace("_", " ").title() for key in CITY_BOUNDING_BOXES]
    return TargetsOut(cities=cities, niches=BUSINESS_NICHES)


@app.get("/api/search-history", response_model=list[SearchHistoryOut])
def get_search_history(
    limit: int = Query(default=30, le=100, gt=0),
    db: Session = Depends(get_db),
):
    stmt = select(SearchHistory).order_by(SearchHistory.last_run_at.desc()).limit(limit)
    records = db.execute(stmt).scalars().all()
    return [
        SearchHistoryOut(
            id=r.id,
            niche=r.niche,
            city=r.city,
            last_run_at=r.last_run_at,
            leads_count=r.leads_count,
            status=r.status,
            is_locked=r.is_locked,
            locked_until=r.locked_until,
        )
        for r in records
    ]


@app.get("/api/campaigns/exhausted", response_model=list[ExhaustedCampaignOut])
def get_exhausted_campaigns(db: Session = Depends(get_db)):
    clear_stale_exhaustion(db)
    stmt = select(CampaignTracker).where(CampaignTracker.is_exhausted.is_(True))
    return db.execute(stmt).scalars().all()


@app.get("/api/leads/stats", response_model=LeadStatsOut)
def lead_stats(db: Session = Depends(get_db)):
    """Counts across all leads, independent of how many the dashboard loads."""
    rows = db.execute(
        select(Lead.category, Lead.opted_out, func.count()).group_by(Lead.category, Lead.opted_out)
    ).all()

    by_category: dict[str, int] = {}
    opted_out = 0
    for category, is_opted_out, count in rows:
        if is_opted_out:
            opted_out += count
        else:
            by_category[category] = by_category.get(category, 0) + count

    return LeadStatsOut(total=sum(by_category.values()), by_category=by_category, opted_out=opted_out)


@app.get("/api/leads", response_model=list[LeadOut])
def list_leads(
    category: LeadCategory | None = None,
    status: OutreachStatus | None = None,
    limit: int = Query(default=50, le=1000, gt=0),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    stmt = select(Lead)
    if category:
        stmt = stmt.where(Lead.category == category)
    if status:
        stmt = stmt.where(Lead.status == status)
    stmt = stmt.order_by(Lead.created_at.desc()).limit(limit).offset(offset)

    return db.execute(stmt).scalars().all()


@app.patch("/api/leads/{lead_id}/status", response_model=LeadOut)
def update_lead_status(
    lead_id: uuid.UUID, payload: LeadStatusUpdate, db: Session = Depends(get_db)
):
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead.status = payload.status
    db.commit()
    db.refresh(lead)
    return lead


@app.post("/api/leads/{lead_id}/opt-out", response_model=LeadOut)
def opt_out_lead(lead_id: uuid.UUID, db: Session = Depends(get_db)):
    lead = db.get(Lead, lead_id)
    if lead is None:
        raise HTTPException(status_code=404, detail="Lead not found")

    lead.opted_out = True
    lead.status = "OPTED_OUT"
    db.commit()
    db.refresh(lead)
    return lead
