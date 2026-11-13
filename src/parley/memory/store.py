from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from parley.memory.tables import CustomerMemoryRow

DEFAULT_RECALL = 8


class MemoryFact(BaseModel):
    kind: str
    content: str
    ticket_id: str
    created_at: datetime


def remember(
    session: Session,
    customer_id: int,
    ticket_id: str,
    facts: list[tuple[str, str]],
    now: datetime,
) -> None:
    for kind, content in facts:
        session.add(
            CustomerMemoryRow(
                customer_id=customer_id,
                kind=kind,
                content=content,
                ticket_id=ticket_id,
                created_at=now,
            )
        )
    session.flush()


def recall(session: Session, customer_id: int, limit: int = DEFAULT_RECALL) -> list[MemoryFact]:
    """The newest facts about one customer, newest first."""
    stmt = (
        select(CustomerMemoryRow)
        .where(CustomerMemoryRow.customer_id == customer_id)
        .order_by(CustomerMemoryRow.created_at.desc(), CustomerMemoryRow.id.desc())
        .limit(limit)
    )
    return [
        MemoryFact(kind=r.kind, content=r.content, ticket_id=r.ticket_id, created_at=r.created_at)
        for r in session.scalars(stmt)
    ]


def recall_for_ticket(session: Session, customer_id: int, ticket_id: str) -> list[MemoryFact]:
    """Facts recorded earlier for one ticket, oldest first; a dialogue reruns the same ticket."""
    stmt = (
        select(CustomerMemoryRow)
        .where(
            CustomerMemoryRow.customer_id == customer_id, CustomerMemoryRow.ticket_id == ticket_id
        )
        .order_by(CustomerMemoryRow.id)
    )
    return [
        MemoryFact(kind=r.kind, content=r.content, ticket_id=r.ticket_id, created_at=r.created_at)
        for r in session.scalars(stmt)
    ]


def render_memory(facts: list[MemoryFact]) -> str:
    return "\n".join(f"- {f.created_at.date()} ({f.ticket_id}): {f.content}" for f in facts)
