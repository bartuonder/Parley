from datetime import datetime

from sqlalchemy import ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from parley.db.base import Base
from parley.db.models import tstz

MEMORY_TABLES = frozenset({"customer_memory"})


class CustomerMemoryRow(Base):
    __tablename__ = "customer_memory"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    content: Mapped[str] = mapped_column(Text)
    ticket_id: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(tstz())
