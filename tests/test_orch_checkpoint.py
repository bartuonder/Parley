import asyncio
import json
import uuid
from datetime import timedelta
from typing import Any

from langgraph.types import Command
from sqlalchemy.orm import Session

from parley.agent.ticket import Ticket
from parley.backend.rules import APPROVAL_THRESHOLD_CENTS
from parley.backend.services import Backend
from parley.db.enums import OrderStatus, RefundStatus, ShipmentStatus
from parley.db.models import Order, Refund
from parley.orchestration.checkpoint import postgres_checkpointer
from parley.orchestration.graph import GraphDeps, build_graph
from parley.tools.catalog import default_registry
from parley.tools.context import ToolContext
from tests.conftest import _test_url
from tests.factories import NOW, make_customer, make_item, make_order, make_shipment
from tests.fakes import ScriptedLLM, call_turn, reply_turn


def selector_run(coro: Any) -> Any:
    """psycopg async cannot use the Proactor loop that asyncio picks by default on Windows."""
    return asyncio.run(coro, loop_factory=asyncio.SelectorEventLoop)


def test_paused_ticket_survives_a_restart_and_resumes_from_postgres(session: Session) -> None:
    sender = make_customer(session, "ada@example.com")
    ctx = ToolContext(Backend(session, lambda: NOW + timedelta(days=10)), sender.id, "T-1")
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
            reply_turn('{"approved": true, "issues": []}'),
            reply_turn("Your refund is under review."),
        ]
    )
    deps = GraphDeps(
        router_llm=ScriptedLLM([reply_turn("billing")]),
        llm=llm,
        ctx=ctx,
        registry=default_registry(),
        model="scripted",
        max_steps=8,
        max_cost_usd=1.0,
        max_revisions=2,
    )
    ticket = Ticket(id="T-1", sender_email="ada@example.com", subject="Order", body="Refund.")
    thread = f"T-1-{uuid.uuid4().hex[:8]}"
    config: Any = {"configurable": {"thread_id": thread, "deps": deps}}

    async def first_process() -> str:
        async with postgres_checkpointer(_test_url()) as saver:
            graph = build_graph(saver)
            state = await graph.ainvoke({"ticket": ticket.model_dump()}, config=config)
            return str(state["__interrupt__"][0].value["refunds"][0]["refund_id"])

    async def second_process(refund_id: str) -> dict[str, Any]:
        async with postgres_checkpointer(_test_url()) as saver:
            graph = build_graph(saver)
            return await graph.ainvoke(Command(resume={refund_id: True}), config=config)

    refund_id = selector_run(first_process())
    done = selector_run(second_process(refund_id))
    assert "approved and processed" in done["followup"]
    assert session.get_one(Refund, int(refund_id)).status == RefundStatus.PROCESSED
    assert session.get_one(Order, order.id).status == OrderStatus.REFUNDED
