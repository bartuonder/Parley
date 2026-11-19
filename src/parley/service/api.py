import asyncio
import hmac
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime
from functools import lru_cache
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy import func, select

from parley.backend.rules import APPROVAL_THRESHOLD_CENTS
from parley.db.models import Customer
from parley.observability.tables import TraceSpanRow
from parley.policies.loader import load_policies
from parley.service.core import (
    NewTicket,
    NotAwaitingApprovalError,
    UnknownSenderError,
    event_dicts,
)
from parley.service.runtime import Runtime, open_runtime
from parley.service.tables import (
    AWAITING_APPROVAL,
    FAILED,
    RESOLVED,
    ServiceTicketRow,
)
from parley.settings import get_settings

TERMINAL = {RESOLVED, FAILED, AWAITING_APPROVAL}
POLL_S = 0.25
HEARTBEAT_S = 15.0


class PolicyRef(BaseModel):
    id: str
    version: int
    title: str


class CustomerOut(BaseModel):
    name: str
    email: str


class TicketOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    number: int
    customer_name: str | None = None
    policies: list[PolicyRef] = []
    sender_email: str
    subject: str
    body: str
    status: str
    specialist: str | None
    reply: str
    followup: str
    cost_usd: float
    latency_s: float
    trace_id: str | None
    pending: list[dict[str, Any]]
    result: dict[str, Any]
    error: str | None
    created_at: datetime
    updated_at: datetime


class DecisionIn(BaseModel):
    decisions: dict[str, bool]


class SpanOut(BaseModel):
    span_id: str
    parent_id: str | None
    name: str
    kind: str
    started_at: datetime
    duration_ms: float
    status: str
    attributes: dict[str, Any]


class StatsOut(BaseModel):
    approval_threshold_cents: int = APPROVAL_THRESHOLD_CENTS
    by_status: dict[str, int]
    tickets: int
    total_cost_usd: float
    mean_cost_usd: float
    mean_latency_s: float


def create_app(runtime: Runtime | None = None, api_key: str | None = None) -> FastAPI:
    """The ticket API; pass a runtime to skip the process-level setup (tests do)."""

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if runtime is not None:
            app.state.runtime = runtime
            yield
            return
        async with open_runtime() as opened:
            app.state.runtime = opened
            yield

    key = api_key if api_key is not None else _configured_key()
    app = FastAPI(title="Parley service", version="0.1.0", lifespan=lifespan)

    def require_key(x_api_key: Annotated[str | None, Header()] = None) -> None:
        if key is not None and not hmac.compare_digest(x_api_key or "", key):
            raise HTTPException(status_code=401, detail="invalid or missing API key")

    guard = [Depends(require_key)]

    def rt(request: Request) -> Runtime:
        found: Runtime = request.app.state.runtime
        return found

    RuntimeDep = Annotated[Runtime, Depends(rt)]

    @app.exception_handler(UnknownSenderError)
    async def unknown_sender(_: Request, exc: UnknownSenderError) -> JSONResponse:
        return JSONResponse({"code": "unknown_sender", "detail": str(exc)}, status_code=422)

    @app.exception_handler(NotAwaitingApprovalError)
    async def not_waiting(_: Request, exc: NotAwaitingApprovalError) -> JSONResponse:
        return JSONResponse({"code": "not_awaiting_approval", "detail": str(exc)}, status_code=409)

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.post("/tickets", status_code=202, response_model=TicketOut, dependencies=guard)
    async def create_ticket(body: NewTicket, runtime: RuntimeDep) -> TicketOut:
        return present(runtime, [await runtime.service.submit(body)])[0]

    @app.get("/tickets", response_model=list[TicketOut], dependencies=guard)
    async def list_tickets(
        runtime: RuntimeDep,
        status: str | None = None,
        limit: Annotated[int, Query(ge=1, le=200)] = 50,
    ) -> list[TicketOut]:
        return present(runtime, runtime.service.list_tickets(status, limit))

    @app.get("/customers", response_model=list[CustomerOut], dependencies=guard)
    async def customers(
        runtime: RuntimeDep, limit: Annotated[int, Query(ge=1, le=500)] = 300
    ) -> list[CustomerOut]:
        with runtime.sessions() as session:
            stmt = select(Customer.name, Customer.email).order_by(Customer.name).limit(limit)
            return [CustomerOut(name=n, email=e) for n, e in session.execute(stmt)]

    @app.get("/tickets/{ticket_id}", response_model=TicketOut, dependencies=guard)
    async def get_ticket(ticket_id: str, runtime: RuntimeDep) -> TicketOut:
        return present(runtime, [_found(runtime.service.get_ticket(ticket_id))])[0]

    @app.get("/tickets/{ticket_id}/events", dependencies=guard)
    async def stream_events(
        ticket_id: str,
        request: Request,
        runtime: RuntimeDep,
        last_event_id: Annotated[str | None, Header()] = None,
    ) -> StreamingResponse:
        _found(runtime.service.get_ticket(ticket_id))
        after = int(last_event_id) if last_event_id and last_event_id.isdigit() else 0
        return StreamingResponse(
            _sse(request, runtime, ticket_id, after),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.get("/tickets/{ticket_id}/trace", response_model=list[SpanOut], dependencies=guard)
    async def trace(ticket_id: str, runtime: RuntimeDep) -> list[SpanOut]:
        row = _found(runtime.service.get_ticket(ticket_id))
        if row.trace_id is None:
            return []
        with runtime.sessions() as session:
            stmt = (
                select(TraceSpanRow)
                .where(TraceSpanRow.trace_id == row.trace_id)
                .order_by(TraceSpanRow.started_at, TraceSpanRow.id)
            )
            return [
                SpanOut(
                    span_id=s.span_id,
                    parent_id=s.parent_id,
                    name=s.name,
                    kind=s.kind,
                    started_at=s.started_at,
                    duration_ms=s.duration_ms,
                    status=s.status,
                    attributes=s.attributes,
                )
                for s in session.scalars(stmt)
            ]

    @app.get("/approvals", response_model=list[TicketOut], dependencies=guard)
    async def approvals(runtime: RuntimeDep) -> list[TicketOut]:
        return present(runtime, runtime.service.list_tickets(AWAITING_APPROVAL, 200))

    @app.post("/approvals/{ticket_id}/decision", response_model=TicketOut, dependencies=guard)
    async def decide(ticket_id: str, body: DecisionIn, runtime: RuntimeDep) -> TicketOut:
        _found(runtime.service.get_ticket(ticket_id))
        return present(runtime, [await runtime.service.decide(ticket_id, body.decisions)])[0]

    @app.get("/stats", response_model=StatsOut, dependencies=guard)
    async def stats(runtime: RuntimeDep) -> StatsOut:
        with runtime.sessions() as session:
            counts = {
                status: int(n)
                for status, n in session.execute(
                    select(ServiceTicketRow.status, func.count()).group_by(ServiceTicketRow.status)
                )
            }
            total, cost, latency = session.execute(
                select(
                    func.count(),
                    func.coalesce(func.sum(ServiceTicketRow.cost_usd), 0.0),
                    func.coalesce(func.avg(ServiceTicketRow.latency_s), 0.0),
                )
            ).one()
        return StatsOut(
            by_status=counts,
            tickets=int(total),
            total_cost_usd=float(cost),
            mean_cost_usd=float(cost) / total if total else 0.0,
            mean_latency_s=float(latency),
        )

    return app


@lru_cache
def policy_titles() -> dict[str, tuple[int, str]]:
    return {doc.key: (doc.version, doc.title) for doc in load_policies()}


def present(runtime: Runtime, rows: list[ServiceTicketRow]) -> list[TicketOut]:
    """Tickets as the API shows them: with the customer's name and readable policy titles."""
    emails = {r.sender_email for r in rows}
    with runtime.sessions() as session:
        names = {
            email: name
            for email, name in session.execute(
                select(Customer.email, Customer.name).where(Customer.email.in_(emails))
            )
        }
    titles = policy_titles()
    out = []
    for row in rows:
        ticket = TicketOut.model_validate(row, from_attributes=True)
        ticket.customer_name = names.get(row.sender_email)
        ticket.policies = [
            PolicyRef(id=key.split("@")[0], version=titles[key][0], title=titles[key][1])
            for key in row.result.get("policies", [])
            if key in titles
        ]
        out.append(ticket)
    return out


def _configured_key() -> str | None:
    key = get_settings().api_key
    return key.get_secret_value() if key is not None else None


def _found(row: ServiceTicketRow | None) -> ServiceTicketRow:
    if row is None:
        raise HTTPException(status_code=404, detail="ticket not found")
    return row


async def _sse(
    request: Request, runtime: Runtime, ticket_id: str, after: int
) -> AsyncIterator[str]:
    """Replay stored events, then follow new ones until the ticket stops or the client leaves."""
    idle = 0.0
    while not await request.is_disconnected():
        rows = runtime.service.events_after(ticket_id, after)
        for event in event_dicts(rows):
            after = event["id"]
            yield f"id: {event['id']}\nevent: {event['kind']}\ndata: {_json(event)}\n\n"
        row = runtime.service.get_ticket(ticket_id)
        if row is not None and row.status in TERMINAL and not rows:
            yield f"event: end\ndata: {_json({'status': row.status})}\n\n"
            return
        idle = 0.0 if rows else idle + POLL_S
        if idle >= HEARTBEAT_S:
            idle = 0.0
            yield ": keep-alive\n\n"
        await asyncio.sleep(POLL_S)


def _json(value: Any) -> str:
    return json.dumps(value, default=str, separators=(",", ":"))
