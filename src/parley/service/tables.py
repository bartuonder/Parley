from datetime import datetime
from typing import Any

from sqlalchemy import Float, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from parley.db.base import Base
from parley.db.models import tstz

SERVICE_TABLES = frozenset({"service_tickets", "ticket_events"})

QUEUED, RUNNING, AWAITING_APPROVAL, RESOLVED, FAILED = (
    "queued",
    "running",
    "awaiting_approval",
    "resolved",
    "failed",
)


class ServiceTicketRow(Base):
    __tablename__ = "service_tickets"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    number: Mapped[int] = mapped_column(
        Integer, server_default=text("nextval('service_ticket_number_seq')"), unique=True
    )
    sender_email: Mapped[str] = mapped_column(String(255), index=True)
    subject: Mapped[str] = mapped_column(String(300))
    body: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24), index=True)
    specialist: Mapped[str | None] = mapped_column(String(24))
    reply: Mapped[str] = mapped_column(Text, default="")
    followup: Mapped[str] = mapped_column(Text, default="")
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    latency_s: Mapped[float] = mapped_column(Float, default=0.0)
    trace_id: Mapped[str | None] = mapped_column(String(32))
    pending: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, default=list)
    result: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(tstz())
    updated_at: Mapped[datetime] = mapped_column(tstz())


class TicketEventRow(Base):
    __tablename__ = "ticket_events"
    __table_args__ = (Index("ix_ticket_events_ticket_id_id", "ticket_id", "id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(32))
    data: Mapped[dict[str, Any]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(tstz())
