import asyncio
import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import timedelta
from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.orm import Session

from parley.agent.llm import LLMClient, LLMResponse, Message
from parley.backend.rules import APPROVAL_THRESHOLD_CENTS
from parley.db.enums import OrderStatus, ShipmentStatus
from parley.service.core import (
    Limits,
    NewTicket,
    NotAwaitingApprovalError,
    TicketService,
    UnknownSenderError,
    event_dicts,
)
from parley.service.simulated import SimulatedLLM
from parley.service.tables import AWAITING_APPROVAL, FAILED, RESOLVED
from tests.factories import NOW, make_customer, make_item, make_order, make_shipment
from tests.fakes import ScriptedLLM, call_turn, reply_turn

APPROVE = '{"approved": true, "issues": []}'
LIMITS = Limits(model="scripted", max_steps=8, max_cost_usd=1.0, max_revisions=2)


def service(session: Session, llm: LLMClient, router: LLMClient | None = None) -> TicketService:
    @contextmanager
    def sessions() -> Iterator[Session]:
        yield session

    return TicketService(
        sessions,
        llm=llm,
        router_llm=router or SimulatedLLM(),
        checkpointer=InMemorySaver(),
        limits=LIMITS,
        now=lambda: NOW + timedelta(days=10),
    )


def new(subject: str = "Where is my order?", **extra: Any) -> NewTicket:
    return NewTicket(sender_email="ada@example.com", subject=subject, body="Please help.", **extra)


def run(svc: TicketService, ticket: NewTicket) -> str:
    async def go() -> str:
        row = await svc.submit(ticket)
        await svc.wait_idle()
        return row.id

    return asyncio.run(go())


def test_a_ticket_runs_to_a_reply_and_leaves_an_ordered_event_trail(session: Session) -> None:
    make_customer(session, "ada@example.com")
    svc = service(session, SimulatedLLM())
    ticket_id = run(svc, new())
    row = svc.get_ticket(ticket_id)
    assert row is not None and row.status == RESOLVED
    assert row.reply.startswith("Thanks for writing in") and row.cost_usd > 0
    events = list(event_dicts(svc.events_after(ticket_id)))
    kinds = [e["kind"] for e in events]
    assert kinds[0] == "queued" and kinds[-1] == "status"
    nodes = [e["data"]["node"] for e in events if e["kind"] == "node"]
    assert nodes[:3] == ["triage", "investigate", "critic"] and "respond" in nodes
    assert [e["id"] for e in events] == sorted(e["id"] for e in events)
    later = svc.events_after(ticket_id, after_id=events[2]["id"])
    assert [e.id for e in later] == [e["id"] for e in events[3:]]


def test_an_unknown_sender_is_refused_and_a_repeated_id_is_not_run_twice(
    session: Session,
) -> None:
    svc = service(session, SimulatedLLM())

    async def refuse() -> None:
        with pytest.raises(UnknownSenderError):
            await svc.submit(new())

    asyncio.run(refuse())
    make_customer(session, "ada@example.com")
    first = run(svc, new(id="T-fixed"))
    again = run(svc, new(id="T-fixed", subject="Changed"))
    assert first == again == "T-fixed"
    row = svc.get_ticket("T-fixed")
    assert row is not None and row.subject == "Where is my order?"
    assert [t.id for t in svc.list_tickets()] == ["T-fixed"]


def test_a_large_refund_waits_in_the_queue_and_a_decision_finishes_it(session: Session) -> None:
    sender = make_customer(session, "ada@example.com")
    amount = APPROVAL_THRESHOLD_CENTS + 5000
    order = make_order(session, sender, total_cents=amount)
    make_item(session, order, unit_price_cents=amount)
    make_shipment(session, order, status=ShipmentStatus.DELIVERED, delivered_at=NOW)
    order.status = OrderStatus.DELIVERED
    session.flush()
    args = {"target": "order", "target_id": order.id, "amount_cents": amount, "reason": "late"}
    llm = ScriptedLLM(
        [
            call_turn("propose_refund", json.dumps(args)),
            reply_turn("Draft."),
            reply_turn(APPROVE),
            reply_turn("Your refund is under review."),
        ]
    )
    svc = service(session, llm, ScriptedLLM([reply_turn("shipping")]))
    ticket_id = run(svc, new("Late order"))
    row = svc.get_ticket(ticket_id)
    assert row is not None and row.status == AWAITING_APPROVAL
    assert row.reply == "Your refund is under review."
    assert [p["amount_cents"] for p in row.pending] == [amount]
    assert [t.id for t in svc.list_tickets(status=AWAITING_APPROVAL)] == [ticket_id]

    refund_id = str(row.pending[0]["refund_id"])
    done = asyncio.run(svc.decide(ticket_id, {refund_id: True}))
    assert done.status == RESOLVED and "approved and processed" in done.followup
    assert done.pending == []
    with pytest.raises(NotAwaitingApprovalError):
        asyncio.run(svc.decide(ticket_id, {refund_id: True}))


class BrokenLLM:
    async def complete(self, messages: list[Message], tools: list[dict[str, Any]]) -> LLMResponse:
        raise RuntimeError("provider down")


def test_a_crashing_model_marks_the_ticket_failed_with_the_reason(session: Session) -> None:
    make_customer(session, "ada@example.com")
    svc = service(session, BrokenLLM(), BrokenLLM())
    row = svc.get_ticket(run(svc, new()))
    assert row is not None and row.status == FAILED
    assert row.error is not None and "provider down" in row.error
    kinds = [e.kind for e in svc.events_after(row.id)]
    assert kinds[-1] == "failed"
