from dataclasses import dataclass, field

from parley.backend.services import Backend
from parley.rag.retrieval import Retriever
from parley.tools.permissions import ALL_PERMISSIONS, Permission


@dataclass(frozen=True)
class Escalation:
    reason: str
    summary: str


@dataclass
class ToolContext:
    """Everything a tool may touch for one ticket: the backend and the sender's identity."""

    backend: Backend
    customer_id: int
    ticket_id: str
    allowed: frozenset[Permission] = ALL_PERMISSIONS
    escalations: list[Escalation] = field(default_factory=list)
    retriever: Retriever | None = None
