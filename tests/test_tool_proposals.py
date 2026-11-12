from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from parley.backend.rules import APPROVAL_THRESHOLD_CENTS
from parley.backend.services import Backend
from parley.db.enums import OrderStatus, ShipmentStatus, SubscriptionStatus
from parley.db.models import Order, Refund
from parley.tools.context import ToolContext
from parley.tools.proposals import PROPOSAL_TOOLS
from parley.tools.registry import ToolRegistry
from tests.factories import (
    NOW,
    make_customer,
    make_item,
    make_order,
    make_shipment,
    make_subscription,
)

REGISTRY = ToolRegistry(PROPOSAL_TOOLS)


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


def refund_args(order: Order, amount: int) -> dict[str, object]:
    return {"target": "order", "target_id": order.id, "amount_cents": amount, "reason": "late"}


def refund_rows(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Refund)) or 0


def test_valid_refund_is_recorded_without_touching_the_database(
    session: Session, ctx: ToolContext
) -> None:
    order = delivered_order(session, ctx)
    result = REGISTRY.call(ctx, "propose_refund", refund_args(order, 5000))
    assert result.ok and result.data is not None
    assert result.data["recorded"] is True and result.data["awaiting_approval"] is False
    assert [p.kind for p in ctx.proposals] == ["issue_refund"]
    assert refund_rows(session) == 0
    assert session.get_one(Order, order.id).status == OrderStatus.DELIVERED


def test_large_refund_is_flagged_as_awaiting_approval(session: Session, ctx: ToolContext) -> None:
    amount = APPROVAL_THRESHOLD_CENTS + 1000
    order = delivered_order(session, ctx, amount)
    result = REGISTRY.call(ctx, "propose_refund", refund_args(order, amount))
    assert result.data is not None and result.data["awaiting_approval"] is True


def test_repeating_a_proposal_does_not_duplicate_it(session: Session, ctx: ToolContext) -> None:
    order = delivered_order(session, ctx)
    REGISTRY.call(ctx, "propose_refund", refund_args(order, 5000))
    again = REGISTRY.call(ctx, "propose_refund", refund_args(order, 5000))
    assert again.data is not None and again.data["duplicate"] is True
    assert len(ctx.proposals) == 1


def test_ineligible_or_oversized_refunds_are_rejected_at_proposal_time(
    session: Session, ctx: ToolContext
) -> None:
    order = delivered_order(session, ctx)
    too_much = REGISTRY.call(ctx, "propose_refund", refund_args(order, 9000))
    assert too_much.error_code == "invalid_request"
    ctx.backend.now = lambda: NOW + timedelta(days=90)
    expired = REGISTRY.call(ctx, "propose_refund", refund_args(order, 5000))
    assert expired.error_code == "not_eligible" and expired.message == "window_expired"
    assert ctx.proposals == []


def test_other_customers_records_cannot_be_proposed_on(session: Session, ctx: ToolContext) -> None:
    other = make_order(session, make_customer(session, "bob@example.com"), total_cents=5000)
    result = REGISTRY.call(ctx, "propose_refund", refund_args(other, 5000))
    assert result.error_code == "access_denied" and ctx.proposals == []


def test_cancellation_is_recorded_unless_already_cancelled(
    session: Session, ctx: ToolContext
) -> None:
    sub = make_subscription(session, ctx.backend.get_customer(ctx.customer_id))
    assert REGISTRY.call(ctx, "propose_cancel_subscription", {"subscription_id": sub.id}).ok
    sub.status = SubscriptionStatus.CANCELLED
    session.flush()
    again = REGISTRY.call(ctx, "propose_cancel_subscription", {"subscription_id": sub.id})
    assert again.error_code == "invalid_request"
    assert [p.kind for p in ctx.proposals] == ["cancel_subscription"]


def test_escalation_is_recorded_with_reason_and_summary(ctx: ToolContext) -> None:
    args = {"reason": "legal_threat", "summary": "Mentions a lawyer"}
    assert REGISTRY.call(ctx, "propose_escalation", args).ok
    assert ctx.proposals[0].arguments == args
    assert ctx.escalations == []
