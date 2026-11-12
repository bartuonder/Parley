import asyncio
import json
from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from parley.agent.result import AgentResult, StopReason
from parley.agent.ticket import Ticket
from parley.backend.rules import APPROVAL_THRESHOLD_CENTS
from parley.backend.services import Backend
from parley.db.enums import OrderStatus, ShipmentStatus
from parley.orchestration.runner import run_multi
from parley.tools.context import ToolContext
from tests.factories import NOW, make_customer, make_item, make_order, make_shipment
from tests.fakes import ScriptedLLM, call_turn, reply_turn

TICKET = Ticket(id="T-1", sender_email="ada@example.com", subject="Order", body="Refund please.")
APPROVE = '{"approved": true, "issues": []}'


@pytest.fixture
def ctx(session: Session) -> ToolContext:
    sender = make_customer(session, "ada@example.com")
    return ToolContext(Backend(session, lambda: NOW + timedelta(days=10)), sender.id, "T-1")


def order_for(session: Session, ctx: ToolContext, price: int) -> int:
    order = make_order(session, ctx.backend.get_customer(ctx.customer_id), total_cents=price)
    make_item(session, order, unit_price_cents=price)
    make_shipment(session, order, status=ShipmentStatus.DELIVERED, delivered_at=NOW)
    order.status = OrderStatus.DELIVERED
    session.flush()
    return order.id


def go(ctx: ToolContext, llm: ScriptedLLM) -> AgentResult:
    return asyncio.run(
        run_multi(
            ScriptedLLM([reply_turn("shipping")]),
            llm,
            ctx,
            TICKET,
            model="scripted",
            max_steps=8,
            max_cost_usd=1.0,
            max_revisions=2,
        )
    )


def test_result_maps_the_graph_state_to_the_scoring_format(
    session: Session, ctx: ToolContext
) -> None:
    order_id = order_for(session, ctx, 5000)
    args = {"target": "order", "target_id": order_id, "amount_cents": 5000, "reason": "late"}
    llm = ScriptedLLM(
        [
            call_turn("propose_refund", json.dumps(args)),
            reply_turn("Draft."),
            reply_turn(APPROVE),
            reply_turn("Your refund of $50.00 was processed."),
        ]
    )
    result = go(ctx, llm)
    names = [c.name for c in result.tool_calls]
    assert names == ["propose_refund", "issue_refund"]
    assert result.stop_reason == StopReason.REPLY
    assert result.reply.startswith("Your refund")
    assert result.extras["specialist"] == "shipping"
    assert result.extras["revisions"] == 0 and not result.extras["awaiting_approval"]
    assert result.usage.cost_usd > 0


def test_a_paused_approval_still_returns_the_customer_reply(
    session: Session, ctx: ToolContext
) -> None:
    amount = APPROVAL_THRESHOLD_CENTS + 5000
    order_id = order_for(session, ctx, amount)
    args = {"target": "order", "target_id": order_id, "amount_cents": amount, "reason": "late"}
    llm = ScriptedLLM(
        [
            call_turn("propose_refund", json.dumps(args)),
            reply_turn("Draft."),
            reply_turn(APPROVE),
            reply_turn("Your refund is under review."),
        ]
    )
    result = go(ctx, llm)
    assert result.extras["awaiting_approval"] is True
    assert result.reply == "Your refund is under review."
