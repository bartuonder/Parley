from dataclasses import dataclass, field
from typing import Any

from parley.backend.services import Backend
from parley.rag.retrieval import Retriever
from parley.security.guards import GuardConfig
from parley.security.redact import redact
from parley.tools.permissions import ALL_PERMISSIONS, Permission


@dataclass(frozen=True)
class Escalation:
    reason: str
    summary: str


@dataclass(frozen=True)
class Proposal:
    """An action a specialist wants taken; it runs only after review."""

    kind: str
    arguments: dict[str, Any]


@dataclass
class ToolContext:
    """Everything a tool may touch for one ticket: the backend and the sender's identity."""

    backend: Backend
    customer_id: int
    ticket_id: str
    allowed: frozenset[Permission] = ALL_PERMISSIONS
    escalations: list[Escalation] = field(default_factory=list)
    retriever: Retriever | None = None
    proposals: list[Proposal] = field(default_factory=list)
    guards: GuardConfig = field(default_factory=GuardConfig.off)
    write_locked: bool = False
    guard_events: list[str] = field(default_factory=list)

    def clean(self, text: str) -> str:
        """Mask other people's personal data before text is stored in a record."""
        if not self.guards.redact_records:
            return text
        return redact(text, keep=[self.backend.get_customer(self.customer_id).email])
