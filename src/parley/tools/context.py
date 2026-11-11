from dataclasses import dataclass

from parley.backend.services import Backend
from parley.tools.permissions import ALL_PERMISSIONS, Permission


@dataclass
class ToolContext:
    """Everything a tool may touch for one ticket: the backend and the sender's identity."""

    backend: Backend
    customer_id: int
    ticket_id: str
    allowed: frozenset[Permission] = ALL_PERMISSIONS
