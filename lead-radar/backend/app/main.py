from datetime import datetime, timedelta, timezone
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
from app.db.models import Lead, SearchHistory
from app.db.session import get_db
from app.services.discovery.geo_grid import generate_city_cells
from app.worker import QUEUE_NAME, process_h3_cell

app = FastAPI(title=settings.PROJECT_NAME)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

redis_conn = Redis.from_url(settings.REDIS_URL)
task_queue = Queue(QUEUE_NAME, connection=redis_conn)

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
    query: str
    city: str
    max_cells: int = Field(default=6, le=6, ge=1)


class ScrapeTriggerResponse(BaseModel):
    task_ids: list[str]
    cells_queued: int


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


class LeadStatusUpdate(BaseModel):
    status: OutreachStatus


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
    norm_niche = payload.query.strip().lower()
    norm_city = payload.city.strip().lower()

    # 1. Daily Execution Lock Check (24-hour lock per niche + city)
    history = db.execute(
        select(SearchHistory).where(
            func.lower(SearchHistory.niche) == norm_niche,
            func.lower(SearchHistory.city) == norm_city,
        )
    ).scalar_one_or_none()

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

    # 2. Generate H3 cells (strictly capped at max 6 cells)
    try:
        cells = generate_city_cells(payload.city)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    max_cells = min(max(1, payload.max_cells), 6)
    selected_cells = cells[:max_cells]

    # Pre-seed seen_cells in Redis to prevent spatial expansion from re-running initial cells
    seen_cells_key = f"seen_cells:{norm_city}:{norm_niche}"
    for hex_id in selected_cells:
        redis_conn.sadd(seen_cells_key, hex_id)

    # 3. Update or create SearchHistory lock
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

    # 4. Enqueue initial H3 cells to RQ
    jobs = [
        task_queue.enqueue(process_h3_cell, hex_id, payload.query, payload.city, 0)
        for hex_id in selected_cells
    ]

    return ScrapeTriggerResponse(
        task_ids=[job.id for job in jobs],
        cells_queued=len(jobs),
    )


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


@app.get("/api/leads", response_model=list[LeadOut])
def list_leads(
    category: str | None = None,
    status: str | None = None,
    limit: int = Query(default=50, le=200, gt=0),
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
