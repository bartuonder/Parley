import asyncio
import json
from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from parley.agent.loop import run_ticket
from parley.agent.result import AgentResult, StopReason
from parley.agent.ticket import Ticket
from parley.backend.services import Backend
from parley.db.enums import OrderStatus, ShipmentStatus
from parley.db.models import Order
from parley.tools.catalog import default_registry
from parley.tools.context import ToolContext
from tests.factories import NOW, make_customer, make_item, make_order, make_shipment
from tests.fakes import ScriptedLLM, call_turn, reply_turn

TICKET = Ticket(id="T-1", sender_email="ada@example.com", subject="Refund", body="Refund please")


@pytest.fixture
def ctx(session: Session) -> ToolContext:
    sender = make_customer(session, "ada@example.com")
    return ToolContext(Backend(session, lambda: NOW + timedelta(days=10)), sender.id, "T-1")


def delivered_order(session: Session, ctx: ToolContext, price: int = 5000) -> Order:
    order = make_order(session, ctx.backend.get_customer(ctx.customer_id), total_cents=price)
    make_item(session, order, unit_price_cents=price)
    make_shipment(session, order, status=ShipmentStatus.DELIVERED, delivered_at=NOW)
    order.status = OrderStatus.DELIVERED
    session.flush()
    return order


def run(
    llm: ScriptedLLM, ctx: ToolContext, max_steps: int = 6, max_cost_usd: float = 1.0
) -> AgentResult:
    return asyncio.run(
        run_ticket(
            llm,
            default_registry(),
            ctx,
            TICKET,
            model="scripted",
            max_steps=max_steps,
            max_cost_usd=max_cost_usd,
        )
    )


def test_tool_call_then_reply_is_traced_and_priced(session: Session, ctx: ToolContext) -> None:
    order = delivered_order(session, ctx)
    llm = ScriptedLLM(
        [call_turn("get_order", json.dumps({"order_id": order.id})), reply_turn("All good.")]
    )
    result = run(llm, ctx)
    assert result.stop_reason == StopReason.REPLY and result.reply == "All good."
    assert result.steps == 2 and [c.name for c in result.tool_calls] == ["get_order"]
    assert result.usage.prompt_tokens == 200 and result.usage.cost_usd == pytest.approx(0.002)
    second_request = llm.requests[1]
    assert second_request[-1]["role"] == "tool" and second_request[-1]["tool_call_id"] == "c1"
    assert second_request[0]["role"] == "system" and "<ticket_body>" in second_request[1]["content"]


def test_refund_through_the_loop_changes_the_database(session: Session, ctx: ToolContext) -> None:
    order = delivered_order(session, ctx, 5000)
    args = {"target": "order", "target_id": order.id, "amount_cents": 5000, "reason": "late"}
    result = run(
        ScriptedLLM([call_turn("issue_refund", json.dumps(args)), reply_turn("Refunded.")]), ctx
    )
    assert result.tool_calls[0].ok and result.tool_calls[0].output["status"] == "processed"
    assert session.get_one(Order, order.id).status == OrderStatus.REFUNDED


def test_malformed_arguments_are_reported_back_and_the_loop_continues(ctx: ToolContext) -> None:
    llm = ScriptedLLM([call_turn("get_order", "{not json"), reply_turn("Sorry, retrying.")])
    result = run(llm, ctx)
    assert result.stop_reason == StopReason.REPLY
    assert not result.tool_calls[0].ok
    assert result.tool_calls[0].output["error_code"] == "invalid_arguments"
    assert "invalid_arguments" in llm.requests[1][-1]["content"]


def test_escalations_are_returned_with_the_result(ctx: ToolContext) -> None:
    args = {"reason": "legal_threat", "summary": "Mentions a lawyer"}
    llm = ScriptedLLM(
        [call_turn("escalate_to_human", json.dumps(args)), reply_turn("A human will help.")]
    )
    result = run(llm, ctx)
    assert [(e.reason, e.summary) for e in result.escalations] == [
        ("legal_threat", "Mentions a lawyer")
    ]


def test_step_limit_stops_a_looping_model(ctx: ToolContext) -> None:
    llm = ScriptedLLM([call_turn("get_customer_overview", "{}", f"c{i}") for i in range(5)])
    result = run(llm, ctx, max_steps=3)
    assert result.stop_reason == StopReason.MAX_STEPS and result.steps == 3
    assert result.reply == "" and len(result.tool_calls) == 3


def test_cost_limit_stops_before_running_more_tools(session: Session, ctx: ToolContext) -> None:
    order = delivered_order(session, ctx)
    args = {"target": "order", "target_id": order.id, "amount_cents": 5000, "reason": "late"}
    llm = ScriptedLLM([call_turn("issue_refund", json.dumps(args), cost_usd=0.5), reply_turn("x")])
    result = run(llm, ctx, max_cost_usd=0.1)
    assert result.stop_reason == StopReason.BUDGET and result.tool_calls == []
    assert session.get_one(Order, order.id).status == OrderStatus.DELIVERED


def test_custom_system_prompt_and_notes_reach_the_model(ctx: ToolContext) -> None:
    llm = ScriptedLLM([reply_turn("ok")])
    asyncio.run(
        run_ticket(
            llm,
            default_registry(),
            ctx,
            TICKET,
            model="scripted",
            max_steps=3,
            max_cost_usd=1.0,
            system="Custom rules.",
            notes="Reviewer note: cite the policy.",
        )
    )
    system, user = llm.requests[0]
    assert system["content"] == "Custom rules."
    assert user["content"].endswith("Reviewer note: cite the policy.")
    assert "<ticket_body>" in user["content"]
