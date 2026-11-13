import asyncio
import json
from datetime import timedelta
from typing import Any

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command
from sqlalchemy.orm import Session

from parley.agent.ticket import Ticket
from parley.backend.rules import APPROVAL_THRESHOLD_CENTS
from parley.backend.services import Backend
from parley.db.enums import OrderStatus, RefundStatus, ShipmentStatus
from parley.db.models import Order, Refund
from parley.memory.store import recall
from parley.orchestration.graph import GraphDeps, build_graph
from parley.tools.catalog import default_registry
from parley.tools.context import ToolContext
from tests.factories import NOW, make_customer, make_item, make_order, make_shipment
from tests.fakes import ScriptedLLM, call_turn, reply_turn

APPROVE = '{"approved": true, "issues": []}'


def reject(issue: str) -> str:
    return json.dumps({"approved": False, "issues": [issue]})


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


def propose_refund(order: Order, amount: int, call_id: str = "p1") -> Any:
    args = {"target": "order", "target_id": order.id, "amount_cents": amount, "reason": "late"}
    return call_turn("propose_refund", json.dumps(args), call_id)


def propose_handover(call_id: str = "h1") -> Any:
    args = {"reason": "legal_threat", "summary": "Customer mentions a lawyer"}
    return call_turn("propose_escalation", json.dumps(args), call_id)


def ticket(body: str = "Please refund my order.") -> Ticket:
    return Ticket(id="T-1", sender_email="ada@example.com", subject="Order", body=body)


def deps(
    ctx: ToolContext, router: ScriptedLLM, llm: ScriptedLLM, max_revisions: int = 2
) -> GraphDeps:
    return GraphDeps(
        router_llm=router,
        llm=llm,
        ctx=ctx,
        registry=default_registry(),
        model="scripted",
        max_steps=8,
        max_cost_usd=1.0,
        max_revisions=max_revisions,
    )


def run(
    d: GraphDeps, t: Ticket, checkpointer: InMemorySaver | None = None, resume: Any = None
) -> dict[str, Any]:
    graph = build_graph(checkpointer)
    config: Any = {"configurable": {"thread_id": t.id, "deps": d}}
    payload: Any = Command(resume=resume) if resume is not None else {"ticket": t.model_dump()}
    return asyncio.run(graph.ainvoke(payload, config=config))


def test_happy_path_routes_proposes_reviews_executes_and_replies(
    session: Session, ctx: ToolContext
) -> None:
    order = delivered_order(session, ctx)
    llm = ScriptedLLM(
        [
            call_turn("get_customer_overview", "{}"),
            propose_refund(order, 5000),
            reply_turn("I have asked for a refund of $50.00."),
            reply_turn(APPROVE),
            reply_turn("Your refund of $50.00 was processed."),
        ]
    )
    state = run(deps(ctx, ScriptedLLM([reply_turn("billing")]), llm), ticket())
    assert state["specialist"] == "billing" and state["verdict"]["approved"]
    assert [a["kind"] for a in state["actions"]] == ["issue_refund"] and state["actions"][0]["ok"]
    assert state["reply"] == "Your refund of $50.00 was processed."
    assert session.get_one(Order, order.id).status == OrderStatus.REFUNDED
    assert state["usage"]["cost_usd"] > 0 and "__interrupt__" not in state


def test_specialist_cannot_change_anything_before_review(
    session: Session, ctx: ToolContext
) -> None:
    order = delivered_order(session, ctx)
    llm = ScriptedLLM(
        [
            propose_refund(order, 5000),
            reply_turn("Draft."),
            reply_turn(reject("Window?")),
            propose_refund(order, 5000),
            reply_turn("Draft."),
            reply_turn(reject("Still no.")),
            propose_refund(order, 5000),
            reply_turn("Draft."),
            reply_turn(reject("No.")),
            reply_turn("A human agent will follow up."),
        ]
    )
    state = run(deps(ctx, ScriptedLLM([reply_turn("billing")]), llm), ticket())
    assert state["revisions"] == 3
    assert [a["kind"] for a in state["actions"]] == ["escalate_to_human"]
    assert session.get_one(Order, order.id).status == OrderStatus.DELIVERED
    assert "could not approve the plan after 3 tries" in state["actions"][0]["arguments"]["summary"]


def test_critic_feedback_reaches_the_specialist_on_revision(
    session: Session, ctx: ToolContext
) -> None:
    order = delivered_order(session, ctx)
    specialist = ScriptedLLM(
        [
            propose_refund(order, 5000),
            reply_turn("Draft one."),
            reply_turn(reject("Hand this over instead.")),
            propose_handover(),
            reply_turn("Draft two."),
            reply_turn(APPROVE),
            reply_turn("A human will follow up."),
        ]
    )
    state = run(deps(ctx, ScriptedLLM([reply_turn("billing")]), specialist), ticket())
    assert state["revisions"] == 1 and [a["kind"] for a in state["actions"]] == [
        "escalate_to_human"
    ]
    second_run_user_message = specialist.requests[3][1]["content"]
    assert (
        "Reviewer feedback" in second_run_user_message
        and "Hand this over" in second_run_user_message
    )
    assert ctx.escalations and ctx.escalations[0].reason == "legal_threat"


def test_legal_threat_is_caught_by_rules_without_a_model_call(
    session: Session, ctx: ToolContext
) -> None:
    order = delivered_order(session, ctx)
    llm = ScriptedLLM(
        [
            propose_refund(order, 5000),
            reply_turn("Refund coming."),
            propose_handover(),
            reply_turn("A human will take over."),
            reply_turn(APPROVE),
            reply_turn("A human agent will follow up."),
        ]
    )
    body = "Refund today or I will contact my lawyer."
    state = run(deps(ctx, ScriptedLLM([reply_turn("billing")]), llm), ticket(body))
    assert state["revisions"] == 1
    assert [a["kind"] for a in state["actions"]] == ["escalate_to_human"]
    assert session.get_one(Order, order.id).status == OrderStatus.DELIVERED


def test_unfinished_specialist_is_replaced_by_a_handover(
    session: Session, ctx: ToolContext
) -> None:
    looping = ScriptedLLM([call_turn("get_customer_overview", "{}", f"c{i}") for i in range(8)])
    looping._turns += [reply_turn(APPROVE), reply_turn("A human agent will follow up.")]
    state = run(deps(ctx, ScriptedLLM([reply_turn("billing")]), looping), ticket())
    assert state["stop_reason"] == "max_steps"
    assert [a["kind"] for a in state["actions"]] == ["escalate_to_human"]


def test_large_refund_replies_then_waits_for_a_human_and_resumes(
    session: Session, ctx: ToolContext
) -> None:
    amount = APPROVAL_THRESHOLD_CENTS + 5000
    order = delivered_order(session, ctx, amount)
    llm = ScriptedLLM(
        [
            propose_refund(order, amount),
            reply_turn("I have asked for a refund."),
            reply_turn(APPROVE),
            reply_turn("Your refund of $250.00 is under review."),
        ]
    )
    saver = InMemorySaver()
    d = deps(ctx, ScriptedLLM([reply_turn("billing")]), llm)
    paused = run(d, ticket(), saver)
    assert paused["reply"] == "Your refund of $250.00 is under review."
    [interrupt] = paused["__interrupt__"]
    refund_id = interrupt.value["refunds"][0]["refund_id"]
    assert interrupt.value["refunds"][0]["amount"] == "$250.00"
    assert session.get_one(Order, order.id).status == OrderStatus.DELIVERED

    done = run(d, ticket(), saver, resume={str(refund_id): True})
    assert "approved and processed" in done["followup"]
    assert session.get_one(Refund, refund_id).status == RefundStatus.PROCESSED
    assert session.get_one(Order, order.id).status == OrderStatus.REFUNDED


def test_a_rejected_approval_leaves_the_order_untouched(session: Session, ctx: ToolContext) -> None:
    amount = APPROVAL_THRESHOLD_CENTS + 5000
    order = delivered_order(session, ctx, amount)
    llm = ScriptedLLM(
        [
            propose_refund(order, amount),
            reply_turn("Draft."),
            reply_turn(APPROVE),
            reply_turn("Under review."),
        ]
    )
    saver = InMemorySaver()
    d = deps(ctx, ScriptedLLM([reply_turn("billing")]), llm)
    paused = run(d, ticket(), saver)
    refund_id = paused["__interrupt__"][0].value["refunds"][0]["refund_id"]
    done = run(d, ticket(), saver, resume={str(refund_id): False})
    assert "declined" in done["followup"]
    assert session.get_one(Refund, refund_id).status == RefundStatus.REJECTED
    assert session.get_one(Order, order.id).status == OrderStatus.DELIVERED


def test_outcomes_are_remembered_and_shown_to_the_specialist_next_time(
    session: Session, ctx: ToolContext
) -> None:
    order = delivered_order(session, ctx)
    first = ScriptedLLM(
        [
            propose_refund(order, 5000),
            reply_turn("Draft."),
            reply_turn(APPROVE),
            reply_turn("Done."),
        ]
    )
    run(deps(ctx, ScriptedLLM([reply_turn("billing")]), first), ticket())
    facts = recall(session, ctx.customer_id)
    assert [f.kind for f in facts] == ["refund_issued"] and facts[0].ticket_id == "T-1"

    second = ScriptedLLM([reply_turn("Draft."), reply_turn(APPROVE), reply_turn("Hello.")])
    followup = Ticket(id="T-2", sender_email="ada@example.com", subject="Update", body="Any news?")
    run(deps(ctx, ScriptedLLM([reply_turn("billing")]), second), followup)
    system_prompt = second.requests[0][0]["content"]
    assert "earlier tickets" in system_prompt and "Refund of $50.00" in system_prompt


def test_the_human_decision_is_remembered(session: Session, ctx: ToolContext) -> None:
    amount = APPROVAL_THRESHOLD_CENTS + 5000
    order = delivered_order(session, ctx, amount)
    llm = ScriptedLLM(
        [
            propose_refund(order, amount),
            reply_turn("Draft."),
            reply_turn(APPROVE),
            reply_turn("Under review."),
        ]
    )
    saver = InMemorySaver()
    d = deps(ctx, ScriptedLLM([reply_turn("billing")]), llm)
    paused = run(d, ticket(), saver)
    assert [f.kind for f in recall(session, ctx.customer_id)] == ["refund_pending"]

    refund_id = paused["__interrupt__"][0].value["refunds"][0]["refund_id"]
    run(d, ticket(), saver, resume={str(refund_id): False})
    kinds = [f.kind for f in recall(session, ctx.customer_id)]
    assert kinds == ["refund_declined", "refund_pending"]
