import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    Integer,
    JSON,
    String,
    Text,
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
