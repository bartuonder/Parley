import asyncio
import uuid
from collections.abc import Awaitable, Callable, Iterator
from contextlib import AbstractContextManager
from datetime import datetime
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from parley.agent.llm import LLMClient
from parley.agent.result import CITATION, AgentResult
from parley.agent.ticket import Ticket
from parley.backend.services import Backend, NotFoundError
from parley.observability.llm import TracedLLM
from parley.observability.tracing import span
from parley.orchestration.runner import resume_multi, run_multi
from parley.rag.retrieval import Retriever
from parley.security.guards import GuardConfig
from parley.service.tables import (
    AWAITING_APPROVAL,
    FAILED,
    QUEUED,
    RESOLVED,
    RUNNING,
    ServiceTicketRow,
    TicketEventRow,
)
from parley.tools.context import ToolContext

SessionFactory = Callable[[], AbstractContextManager[Session]]
RetrieverFactory = Callable[[Session], Retriever | None]
Clock = Callable[[], datetime]


class NewTicket(BaseModel):
    sender_email: str = Field(min_length=3, max_length=255, pattern=r"^[^@\s]+@[^@\s]+$")
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=8000)
    id: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")


class UnknownSenderError(Exception):
    """No customer has the sender's email address."""


class NotAwaitingApprovalError(Exception):
    """A decision arrived for a ticket that is not waiting for one."""


class Limits(BaseModel):
    model: str
    max_steps: int
    max_cost_usd: float
    max_revisions: int


class TicketService:
    """Runs tickets through the multi-agent graph and keeps their state, events and cost."""

    def __init__(
        self,
        sessions: SessionFactory,
        *,
        llm: LLMClient,
        router_llm: LLMClient,
        checkpointer: BaseCheckpointSaver[Any],
        limits: Limits,
        now: Clock,
        retriever: RetrieverFactory = lambda _: None,
        guards: GuardConfig | None = None,
        max_concurrency: int = 8,
    ) -> None:
        self._sessions = sessions
        self._llm = TracedLLM(llm)
        self._router = TracedLLM(router_llm)
        self._saver = checkpointer
        self._limits = limits
        self._now = now
        self._retriever = retriever
        self._guards = guards or GuardConfig()
        self._tasks: set[asyncio.Task[None]] = set()
        self._slots = asyncio.Semaphore(max_concurrency)

    async def submit(self, new: NewTicket) -> ServiceTicketRow:
        """Store a ticket and start working on it in the background."""
        with self._sessions() as session:
            if new.id and (existing := session.get(ServiceTicketRow, new.id)):
                return existing
            try:
                Backend(session, self._now).find_customer_by_email(new.sender_email)
            except NotFoundError as exc:
                raise UnknownSenderError(new.sender_email) from exc
            row = ServiceTicketRow(
                id=new.id or f"T-{uuid.uuid4().hex[:12]}",
                sender_email=new.sender_email.lower(),
                subject=new.subject,
                body=new.body,
                status=QUEUED,
                created_at=self._now(),
                updated_at=self._now(),
            )
            session.add(row)
            self._event(session, row.id, "queued", {})
            session.commit()
        task = asyncio.create_task(self.process(row.id))
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return row

    def recover(self) -> int:
        """Fail tickets a stopped process left half done, so none stays 'running' forever."""
        with self._sessions() as session:
            stale = list(
                session.scalars(
                    select(ServiceTicketRow).where(ServiceTicketRow.status.in_([QUEUED, RUNNING]))
                )
            )
            for row in stale:
                row.error = "interrupted by a restart"
                self._set_status(session, row, FAILED)
                self._event(session, row.id, "failed", {"error": row.error})
            session.commit()
            return len(stale)

    async def wait_idle(self) -> None:
        """Wait for every running ticket; used by tests and a clean shutdown."""
        while self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    async def process(self, ticket_id: str) -> None:
        async with self._slots:
            await self._process(ticket_id)

    async def _process(self, ticket_id: str) -> None:
        with self._sessions() as session:
            row = self._get(session, ticket_id)
            ticket = _ticket_of(row)
            self._set_status(session, row, RUNNING)
            session.commit()
            try:
                with span("ticket", "ticket", ticket_id=ticket_id) as handle:
                    result = await run_multi(
                        self._router,
                        self._llm,
                        self._context(session, ticket),
                        ticket,
                        checkpointer=self._saver,
                        on_node=self._reporter(ticket_id),
                        **self._limits.model_dump(),
                    )
                    row.trace_id = handle.trace_id
                self._finish(session, row, result)
            except Exception as exc:
                session.rollback()
                self._fail(session, ticket_id, exc)

    async def decide(self, ticket_id: str, decisions: dict[str, bool]) -> ServiceTicketRow:
        """Apply a human decision to the refunds of a waiting ticket and finish it."""
        async with self._slots:
            return await self._decide(ticket_id, decisions)

    async def _decide(self, ticket_id: str, decisions: dict[str, bool]) -> ServiceTicketRow:
        with self._sessions() as session:
            row = self._get(session, ticket_id)
            if row.status != AWAITING_APPROVAL:
                raise NotAwaitingApprovalError(ticket_id)
            ticket = _ticket_of(row)
            self._event(session, ticket_id, "decision", {"decisions": decisions})
            result = await resume_multi(
                self._router,
                self._llm,
                self._context(session, ticket),
                ticket,
                decisions,
                checkpointer=self._saver,
                on_node=self._reporter(ticket_id),
                **self._limits.model_dump(),
            )
            row.followup = str(result.extras.get("followup", ""))
            row.pending = []
            self._set_status(session, row, RESOLVED)
            self._event(session, ticket_id, "resolved", {"followup": row.followup})
            session.commit()
            return row

    def list_tickets(self, status: str | None = None, limit: int = 50) -> list[ServiceTicketRow]:
        with self._sessions() as session:
            stmt = select(ServiceTicketRow).order_by(
                ServiceTicketRow.created_at.desc(), ServiceTicketRow.number.desc()
            )
            if status:
                stmt = stmt.where(ServiceTicketRow.status == status)
            return list(session.scalars(stmt.limit(limit)))

    def get_ticket(self, ticket_id: str) -> ServiceTicketRow | None:
        with self._sessions() as session:
            return session.get(ServiceTicketRow, ticket_id)

    def events_after(self, ticket_id: str, after_id: int = 0) -> list[TicketEventRow]:
        with self._sessions() as session:
            stmt = (
                select(TicketEventRow)
                .where(TicketEventRow.ticket_id == ticket_id, TicketEventRow.id > after_id)
                .order_by(TicketEventRow.id)
            )
            return list(session.scalars(stmt))

    def _context(self, session: Session, ticket: Ticket) -> ToolContext:
        backend = Backend(session, self._now)
        customer = backend.find_customer_by_email(ticket.sender_email)
        return ToolContext(
            backend,
            customer.id,
            ticket.id,
            retriever=self._retriever(session),
            guards=self._guards,
        )

    def _reporter(self, ticket_id: str) -> Callable[[str, dict[str, Any]], Awaitable[None]]:
        async def report(node: str, update: dict[str, Any]) -> None:
            with self._sessions() as session:
                self._event(session, ticket_id, "node", {"node": node, **summarize(node, update)})
                session.commit()

        return report

    def _finish(self, session: Session, row: ServiceTicketRow, result: AgentResult) -> None:
        row.specialist = result.extras.get("specialist")
        row.reply = result.reply
        row.cost_usd = result.usage.cost_usd
        row.latency_s = result.latency_s
        row.result = {
            "actions": [
                {"name": c.name, "arguments": c.arguments, "ok": c.ok} for c in result.tool_calls
            ],
            "escalations": [e.model_dump() for e in result.escalations],
            "critic_issues": result.extras.get("critic_issues", []),
            "guard_events": result.extras.get("guard_events", []),
            "policies": _shown_policies(result),
        }
        waiting = bool(result.extras.get("awaiting_approval"))
        row.pending = _waiting_refunds(result) if waiting else []
        self._event(session, row.id, "reply", {"reply": row.reply, "cost_usd": row.cost_usd})
        self._set_status(session, row, AWAITING_APPROVAL if waiting else RESOLVED)
        session.commit()

    def _fail(self, session: Session, ticket_id: str, exc: Exception) -> None:
        row = self._get(session, ticket_id)
        row.error = f"{type(exc).__name__}: {exc}"[:500]
        self._set_status(session, row, FAILED)
        self._event(session, ticket_id, "failed", {"error": row.error})
        session.commit()

    def _set_status(self, session: Session, row: ServiceTicketRow, status: str) -> None:
        row.status = status
        row.updated_at = self._now()
        self._event(session, row.id, "status", {"status": status})

    def _event(self, session: Session, ticket_id: str, kind: str, data: dict[str, Any]) -> None:
        stamp = self._now()
        session.add(TicketEventRow(ticket_id=ticket_id, kind=kind, data=data, created_at=stamp))
        session.flush()

    @staticmethod
    def _get(session: Session, ticket_id: str) -> ServiceTicketRow:
        row = session.get(ServiceTicketRow, ticket_id)
        if row is None:
            raise KeyError(ticket_id)
        return row


def _ticket_of(row: ServiceTicketRow) -> Ticket:
    return Ticket(id=row.id, sender_email=row.sender_email, subject=row.subject, body=row.body)


def _shown_policies(result: AgentResult) -> list[str]:
    """Policies the reply names; failing that, the best hit when a refund or cancellation ran."""
    named = list(dict.fromkeys(CITATION.findall(result.reply)))
    acted = any(
        c.ok and c.name in ("issue_refund", "cancel_subscription") for c in result.tool_calls
    )
    return named[:3] or (result.cited_policies[:1] if acted else [])


def _waiting_refunds(result: AgentResult) -> list[dict[str, Any]]:
    return [
        {
            "refund_id": int(c.output["id"]),
            "amount_cents": int(c.arguments["amount_cents"]),
            "target": f"{c.arguments['target']} {c.arguments['target_id']}",
        }
        for c in result.tool_calls
        if c.name == "issue_refund" and c.ok and c.output.get("status") == "pending_approval"
    ]


def summarize(node: str, update: dict[str, Any]) -> dict[str, Any]:
    """The small, display-safe part of a node's output that the live timeline shows."""
    if node == "triage":
        return {"specialist": update.get("specialist")}
    if node == "investigate":
        return {
            "tools": [c.get("name") for c in update.get("trace", [])],
            "proposals": len(update.get("proposals", [])),
        }
    if node == "critic":
        verdict = update.get("verdict", {})
        return {"approved": verdict.get("approved"), "issues": update.get("issues", [])}
    if node == "execute":
        return {"actions": [a.get("kind") for a in update.get("actions", [])]}
    return {}


def event_dicts(rows: list[TicketEventRow]) -> Iterator[dict[str, Any]]:
    for r in rows:
        yield {"id": r.id, "kind": r.kind, "data": r.data, "at": r.created_at.isoformat()}
