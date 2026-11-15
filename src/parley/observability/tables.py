from datetime import datetime
from typing import Any

from sqlalchemy import Float, String
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from parley.db.base import Base
from parley.db.models import tstz

TRACE_TABLES = frozenset({"trace_spans"})


class TraceSpanRow(Base):
    __tablename__ = "trace_spans"

    id: Mapped[int] = mapped_column(primary_key=True)
    trace_id: Mapped[str] = mapped_column(String(32), index=True)
    span_id: Mapped[str] = mapped_column(String(16))
    parent_id: Mapped[str | None] = mapped_column(String(16))
    name: Mapped[str] = mapped_column(String(80))
    kind: Mapped[str] = mapped_column(String(20), index=True)
    started_at: Mapped[datetime] = mapped_column(tstz())
    duration_ms: Mapped[float] = mapped_column(Float)
    status: Mapped[str] = mapped_column(String(10))
    attributes: Mapped[dict[str, Any]] = mapped_column(JSONB)
    events: Mapped[list[dict[str, Any]]] = mapped_column(JSONB)
