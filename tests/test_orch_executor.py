from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from parley.backend.rules import APPROVAL_THRESHOLD_CENTS
from parley.backend.services import Backend
from parley.db.enums import OrderStatus, RefundStatus, ShipmentStatus
from parley.db.models import Order
from parley.orchestration.executor import execute_proposals
from parley.tools.catalog import default_registry
from parley.tools.context import Proposal, ToolContext
from tests.factories import NOW, make_customer, make_item, make_order, make_shipment

REGISTRY = default_registry()


@pytest.fixture
def ctx(session: Session) -> ToolContext:
    sender = make_customer(session, "ada@example.com")
    return ToolContext(Backend(session, lambda: NOW + timedelta(days=10)), sender.id, "T-1")


def delivered_order(session: Session, ctx: ToolContext, price: int) -> Order:
    order = make_order(session, ctx.backend.get_customer(ctx.customer_id), total_cents=price)
    make_item(session, order, unit_price_cents=price)
    make_shipment(session, order, status=ShipmentStatus.DELIVERED, delivered_at=NOW)
    order.status = OrderStatus.DELIVERED
    session.flush()
    return order


def refund(order: Order, amount: int) -> Proposal:
    args = {"target": "order", "target_id": order.id, "amount_cents": amount, "reason": "late"}
    return Proposal("issue_refund", args)


def test_refund_proposal_is_carried_out(session: Session, ctx: ToolContext) -> None:
    order = delivered_order(session, ctx, 5000)
    [done] = execute_proposals(REGISTRY, ctx, [refund(order, 5000)])
    assert done.ok and done.output["status"] == RefundStatus.PROCESSED
    assert session.get_one(Order, order.id).status == OrderStatus.REFUNDED


def test_large_refund_reports_awaiting_approval(session: Session, ctx: ToolContext) -> None:
    amount = APPROVAL_THRESHOLD_CENTS + 1000
    order = delivered_order(session, ctx, amount)
    [done] = execute_proposals(REGISTRY, ctx, [refund(order, amount)])
    assert done.awaiting_approval


def test_handovers_run_after_other_actions(session: Session, ctx: ToolContext) -> None:
    order = delivered_order(session, ctx, 5000)
    escalate = Proposal("escalate_to_human", {"reason": "other", "summary": "note"})
    results = execute_proposals(REGISTRY, ctx, [escalate, refund(order, 5000)])
    assert [r.kind for r in results] == ["issue_refund", "escalate_to_human"]
    assert [e.reason for e in ctx.escalations] == ["other"]


def test_a_failing_action_does_not_stop_the_rest(session: Session, ctx: ToolContext) -> None:
    order = delivered_order(session, ctx, 5000)
    ctx.backend.now = lambda: NOW + timedelta(days=90)
    escalate = Proposal("escalate_to_human", {"reason": "other", "summary": "note"})
    results = execute_proposals(REGISTRY, ctx, [refund(order, 5000), escalate])
    assert [(r.kind, r.ok) for r in results] == [
        ("issue_refund", False),
        ("escalate_to_human", True),
    ]
    assert results[0].error_code == "not_eligible"
