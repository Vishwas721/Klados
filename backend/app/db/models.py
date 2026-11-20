import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )

    place_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )
    business_name: Mapped[str] = mapped_column(String(255), nullable=False)
    phone_number: Mapped[str] = mapped_column(String(30), nullable=False)
    email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    website_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    city: Mapped[str] = mapped_column(String(100), default="Bengaluru")

    h3_hex_id: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    latitude: Mapped[float | None] = mapped_column(Float, nullable=True)
    longitude: Mapped[float | None] = mapped_column(Float, nullable=True)

    category: Mapped[str] = mapped_column(
        Enum(
            "DIGITAL_GHOST",
            "DIGITAL_DINOSAUR",
            "LAGGY_UX",
            "AUTOMATION_CANDIDATE",
            name="lead_category",
        ),
        index=True,
        nullable=False,
    )

    has_ssl: Mapped[bool] = mapped_column(Boolean, default=False)
    is_mobile_responsive: Mapped[bool] = mapped_column(Boolean, default=False)
    ttfb_ms: Mapped[int] = mapped_column(Integer, default=0)
    dom_load_time_ms: Mapped[int] = mapped_column(Integer, default=0)
    detected_tech: Mapped[list] = mapped_column(JSON, default=[])
    llm_audit_summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    lacks_chat_widget: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    lacks_booking_flow: Mapped[bool | None] = mapped_column(Boolean, nullable=True)

    origin_source_url: Mapped[str] = mapped_column(Text, nullable=False)
    extraction_timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    opted_out: Mapped[bool] = mapped_column(Boolean, default=False)

    # Call desk: the latest phone outcome and when the lead is due again.
    # INTERESTED | CALL_BACK | NOT_INTERESTED | WRONG_NUMBER | NO_ANSWER
    call_outcome: Mapped[str | None] = mapped_column(String(20), nullable=True, index=True)
    call_attempts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_called_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_call_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    call_notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    status: Mapped[str] = mapped_column(
        Enum(
            "PENDING",
            "AUDITED",
            "CONTACTED_WHATSAPP",
            "CONTACTED_EMAIL",
            "RESPONDED",
            "CONVERTED",
            "OPTED_OUT",
            name="outreach_status",
        ),
        default="PENDING",
        index=True,
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("phone_number", "business_name", name="uq_leads_phone_business"),
    )


class SearchHistory(Base):
    __tablename__ = "search_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    niche: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    city: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    last_run_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    leads_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="COMPLETED")

    __table_args__ = (
        UniqueConstraint("niche", "city", name="uq_search_history_niche_city"),
    )

    @property
    def is_locked(self) -> bool:
        """True if the search was run within the last 24 hours."""
        if not self.last_run_at:
            return False
        # Normalize to UTC
        last_run = self.last_run_at
        if last_run.tzinfo is None:
            last_run = last_run.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - last_run) < timedelta(hours=24)

    @property
    def locked_until(self) -> datetime:
        """Timestamp when this search combination will become available again."""
        last_run = self.last_run_at
        if last_run.tzinfo is None:
            last_run = last_run.replace(tzinfo=timezone.utc)
        return last_run + timedelta(hours=24)


class IntentPost(Base):
    """A public post where someone asks for a website, a fix, or automation.

    Collected by the request radar (app.services.intent) from freelance
    boards, Reddit, HN and the open web. Plain strings instead of enums so
    adding a source or fit doesn't need a type migration; the API validates.
    """

    __tablename__ = "intent_posts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    source: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    external_id: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    body: Mapped[str] = mapped_column(Text, default="")
    author: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # Subreddit, feed name, search query… whatever narrows down "where"
    channel: Mapped[str | None] = mapped_column(String(255), nullable=True)
    posted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    budget_min: Mapped[float | None] = mapped_column(Float, nullable=True)
    budget_max: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)
    budget_usd: Mapped[float | None] = mapped_column(Float, nullable=True)
    bid_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # WEBSITE_BUILD | WEBSITE_FIX | AUTOMATION | OTHER
    fit: Mapped[str] = mapped_column(String(30), nullable=False, index=True)
    score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    signals: Mapped[list] = mapped_column(JSON, default=list)
    is_local: Mapped[bool] = mapped_column(Boolean, default=False)

    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    reply_draft: Mapped[str | None] = mapped_column(Text, nullable=True)

    # NEW | SAVED | REPLIED | WON | DISMISSED
    status: Mapped[str] = mapped_column(String(20), default="NEW", index=True)
    alerted: Mapped[bool] = mapped_column(Boolean, default=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), index=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )

    __table_args__ = (
        UniqueConstraint("source", "external_id", name="uq_intent_posts_source_external"),
    )


class CampaignTracker(Base):
    __tablename__ = "campaign_tracker"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    niche: Mapped[str] = mapped_column(String(255), nullable=False)
    is_exhausted: Mapped[bool] = mapped_column(Boolean, default=False)
    last_scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        UniqueConstraint("niche", "city", name="uq_campaign_tracker_niche_city"),
    )
