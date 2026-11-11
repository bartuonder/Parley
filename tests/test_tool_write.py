from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from parley.backend.rules import APPROVAL_THRESHOLD_CENTS
from parley.backend.services import Backend
from parley.db.enums import OrderStatus, RefundStatus, ShipmentStatus
from parley.db.models import Order, Refund
from parley.tools.context import ToolContext
from parley.tools.permissions import Permission
from parley.tools.registry import ToolRegistry
from parley.tools.write import WRITE_TOOLS
from tests.factories import NOW, make_customer, make_item, make_order, make_shipment

REGISTRY = ToolRegistry(WRITE_TOOLS)


@pytest.fixture
def ctx(session: Session) -> ToolContext:
    sender = make_customer(session, "ada@example.com")
    return ToolContext(Backend(session, lambda: NOW + timedelta(days=10)), sender.id, "T-1")


def own_order(session: Session, ctx: ToolContext, price: int = 5000) -> Order:
    sender = ctx.backend.get_customer(ctx.customer_id)
    order = make_order(session, sender, total_cents=price)
    make_item(session, order, unit_price_cents=price)
    make_shipment(session, order, status=ShipmentStatus.DELIVERED, delivered_at=NOW)
    order.status = OrderStatus.DELIVERED
    session.flush()
    return order


def refund_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Refund)) or 0


def refund_args(order: Order, amount: int) -> dict[str, object]:
    return {"target": "order", "target_id": order.id, "amount_cents": amount, "reason": "late"}


def test_refund_is_processed_and_updates_the_order(session: Session, ctx: ToolContext) -> None:
    order = own_order(session, ctx, 5000)
    result = REGISTRY.call(ctx, "issue_refund", refund_args(order, 5000))
    assert result.ok and result.data is not None
    assert result.data["status"] == RefundStatus.PROCESSED
    assert result.data["created"] is True and result.data["awaiting_approval"] is False
    assert session.get_one(Order, order.id).status == OrderStatus.REFUNDED


def test_large_refund_waits_for_approval(session: Session, ctx: ToolContext) -> None:
    order = own_order(session, ctx, APPROVAL_THRESHOLD_CENTS + 5000)
    result = REGISTRY.call(ctx, "issue_refund", refund_args(order, APPROVAL_THRESHOLD_CENTS + 5000))
    assert result.ok and result.data is not None
    assert result.data["awaiting_approval"] is True
    assert session.get_one(Order, order.id).status == OrderStatus.DELIVERED


def test_repeating_a_refund_replays_the_original(session: Session, ctx: ToolContext) -> None:
    order = own_order(session, ctx, 5000)
    first = REGISTRY.call(ctx, "issue_refund", refund_args(order, 5000))
    second = REGISTRY.call(ctx, "issue_refund", refund_args(order, 5000))
    assert first.data is not None and second.data is not None
    assert second.data["created"] is False
    assert second.data["id"] == first.data["id"]
    assert refund_count(session) == 1


def test_amount_above_the_maximum_is_refused(session: Session, ctx: ToolContext) -> None:
    order = own_order(session, ctx, 5000)
    result = REGISTRY.call(ctx, "issue_refund", refund_args(order, 6000))
    assert result.error_code == "invalid_request"
    assert refund_count(session) == 0


def test_ineligible_order_is_refused(session: Session, ctx: ToolContext) -> None:
    order = own_order(session, ctx, 5000)
    ctx.backend.now = lambda: NOW + timedelta(days=90)
    result = REGISTRY.call(ctx, "issue_refund", refund_args(order, 5000))
    assert result.error_code == "not_eligible" and result.message == "window_expired"


def test_refund_on_another_customers_order_is_denied(session: Session, ctx: ToolContext) -> None:
    other = make_customer(session, "bob@example.com")
    order = make_order(session, other, total_cents=5000)
    result = REGISTRY.call(ctx, "issue_refund", refund_args(order, 5000))
    assert result.error_code == "access_denied"
    assert refund_count(session) == 0


def test_risky_tools_need_risky_permission(session: Session, ctx: ToolContext) -> None:
    order = own_order(session, ctx, 5000)
    ctx.allowed = frozenset({Permission.READ, Permission.WRITE})
    result = REGISTRY.call(ctx, "issue_refund", refund_args(order, 5000))
    assert result.error_code == "permission_denied"
    assert refund_count(session) == 0
