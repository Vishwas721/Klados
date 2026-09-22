import uuid
from typing import Literal

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from redis import Redis
from rq import Queue
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.models import Lead
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
    max_cells: int = 2


class ScrapeTriggerResponse(BaseModel):
    task_ids: list[str]
    cells_queued: int


class LeadStatusUpdate(BaseModel):
    status: OutreachStatus


class LeadOut(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
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
def trigger_scrape(payload: ScrapeTriggerRequest):
    try:
        cells = generate_city_cells(payload.city)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    selected_cells = cells[: payload.max_cells]
    jobs = [
        task_queue.enqueue(process_h3_cell, hex_id, payload.query)
        for hex_id in selected_cells
    ]

    return ScrapeTriggerResponse(
        task_ids=[job.id for job in jobs],
        cells_queued=len(jobs),
    )


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
