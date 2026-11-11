from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from parley.backend.rules import APPROVAL_THRESHOLD_CENTS
from parley.backend.services import Backend
from parley.db.enums import OrderStatus, ShipmentStatus
from parley.tools.context import ToolContext
from parley.tools.read import READ_TOOLS
from parley.tools.registry import ToolRegistry
from tests.factories import (
    NOW,
    make_customer,
    make_item,
    make_order,
    make_shipment,
    make_subscription,
)

REGISTRY = ToolRegistry(READ_TOOLS)


@pytest.fixture
def ctx(session: Session) -> ToolContext:
    sender = make_customer(session, "ada@example.com")
    return ToolContext(Backend(session, lambda: NOW + timedelta(days=10)), sender.id, "T-1")


def own_delivered_order(session: Session, ctx: ToolContext, price: int = 5000) -> int:
    sender = ctx.backend.get_customer(ctx.customer_id)
    order = make_order(session, sender, total_cents=price)
    make_item(session, order, unit_price_cents=price)
    make_shipment(session, order, status=ShipmentStatus.DELIVERED, delivered_at=NOW)
    order.status = OrderStatus.DELIVERED
    session.flush()
    return order.id


def test_overview_covers_only_the_sender(session: Session, ctx: ToolContext) -> None:
    own_id = own_delivered_order(session, ctx)
    make_subscription(session, ctx.backend.get_customer(ctx.customer_id))
    other = make_customer(session, "bob@example.com")
    make_order(session, other)
    result = REGISTRY.call(ctx, "get_customer_overview", {})
    assert result.ok and result.data is not None
    assert result.data["customer"]["email"] == "ada@example.com"
    assert [o["id"] for o in result.data["orders"]] == [own_id]
    assert len(result.data["subscriptions"]) == 1


def test_get_order_returns_items_and_shipments(session: Session, ctx: ToolContext) -> None:
    order_id = own_delivered_order(session, ctx)
    result = REGISTRY.call(ctx, "get_order", {"order_id": order_id})
    assert result.ok and result.data is not None
    assert result.data["items"][0]["name"] == "Desk lamp"
    assert result.data["shipments"][0]["status"] == "delivered"


def test_other_customers_order_is_denied(session: Session, ctx: ToolContext) -> None:
    other_order = make_order(session, make_customer(session, "bob@example.com"))
    result = REGISTRY.call(ctx, "get_order", {"order_id": other_order.id})
    assert result.error_code == "access_denied"
    args = {"target": "order", "target_id": other_order.id}
    assert REGISTRY.call(ctx, "check_refund_eligibility", args).error_code == "access_denied"


def test_shipment_lookup_by_tracking_number(session: Session, ctx: ToolContext) -> None:
    own_delivered_order(session, ctx)
    assert REGISTRY.call(ctx, "get_shipment", {"tracking_number": "TRK-1"}).ok
    assert REGISTRY.call(ctx, "get_shipment", {"tracking_number": "NOPE"}).error_code == "not_found"


def test_eligibility_reports_amount_and_approval_threshold(
    session: Session, ctx: ToolContext
) -> None:
    order_id = own_delivered_order(session, ctx, price=5000)
    result = REGISTRY.call(
        ctx, "check_refund_eligibility", {"target": "order", "target_id": order_id}
    )
    assert result.ok and result.data is not None
    assert result.data["eligible"] is True
    assert result.data["max_refund_cents"] == 5000
    assert result.data["approval_required_above_cents"] == APPROVAL_THRESHOLD_CENTS


def test_eligibility_for_an_unknown_invoice_is_not_found(ctx: ToolContext) -> None:
    result = REGISTRY.call(ctx, "check_refund_eligibility", {"target": "invoice", "target_id": 0})
    assert result.error_code == "not_found"
