from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from parley.backend.services import Backend
from parley.db.enums import OrderStatus, ShipmentStatus
from parley.db.models import Order
from parley.orchestration.router import Specialist
from parley.orchestration.specialists import specialist_registry
from parley.security.guards import GuardConfig
from parley.tools.catalog import default_registry
from parley.tools.context import ToolContext
from tests.factories import NOW, make_customer, make_item, make_order, make_shipment


def context(session: Session, guards: GuardConfig, price: int = 25000) -> tuple[ToolContext, Order]:
    sender = make_customer(session, "ada@example.com")
    ctx = ToolContext(
        Backend(session, lambda: NOW + timedelta(days=10)), sender.id, "T-1", guards=guards
    )
    order = make_order(session, sender, total_cents=price)
    make_item(session, order, unit_price_cents=price)
    make_shipment(session, order, status=ShipmentStatus.DELIVERED, delivered_at=NOW)
    order.status = OrderStatus.DELIVERED
    session.flush()
    return ctx, order


def refund(order: Order, amount: int) -> dict[str, object]:
    return {"target": "order", "target_id": order.id, "amount_cents": amount, "reason": "x"}


def test_splitting_a_large_refund_to_stay_under_the_threshold_is_refused(session: Session) -> None:
    ctx, order = context(session, GuardConfig())
    registry = default_registry()
    assert registry.call(ctx, "issue_refund", refund(order, 12500)).ok
    second = registry.call(ctx, "issue_refund", refund(order, 12500))
    assert not second.ok and second.error_code == "invalid_request"
    assert second.message is not None and "Do not split a refund" in second.message


def test_without_the_guard_the_split_goes_through(session: Session) -> None:
    ctx, order = context(session, GuardConfig().without("limits"))
    registry = default_registry()
    assert registry.call(ctx, "issue_refund", refund(order, 12500)).ok
    assert registry.call(ctx, "issue_refund", refund(order, 12500)).ok


@pytest.mark.parametrize(("first", "second"), [(5000, 5000), (20000, 4000), (10000, 10000)])
def test_partial_refunds_that_stay_within_the_threshold_are_fine(
    session: Session, first: int, second: int
) -> None:
    ctx, order = context(session, GuardConfig())
    registry = default_registry()
    assert registry.call(ctx, "issue_refund", refund(order, first)).ok
    assert registry.call(ctx, "issue_refund", refund(order, second)).ok or first + second > 20000


def test_one_large_refund_is_not_affected_and_waits_for_approval(session: Session) -> None:
    ctx, order = context(session, GuardConfig())
    result = default_registry().call(ctx, "issue_refund", refund(order, 25000))
    assert result.ok and result.data is not None and result.data["awaiting_approval"] is True


def test_the_same_check_applies_when_a_specialist_proposes_the_split(session: Session) -> None:
    ctx, order = context(session, GuardConfig())
    registry = specialist_registry(Specialist.BILLING)
    assert registry.call(ctx, "propose_refund", refund(order, 12500)).ok
    assert registry.call(ctx, "propose_refund", refund(order, 12500)).ok is True
    ctx.proposals.clear()
    assert registry.call(ctx, "propose_refund", refund(order, 12000)).ok
    split = registry.call(ctx, "propose_refund", refund(order, 13000))
    assert split.error_code == "invalid_request"
    assert len(ctx.proposals) == 1


def test_repeating_an_identical_proposal_is_not_mistaken_for_a_split(session: Session) -> None:
    ctx, order = context(session, GuardConfig())
    registry = specialist_registry(Specialist.BILLING)
    assert registry.call(ctx, "propose_refund", refund(order, 12500)).ok
    again = registry.call(ctx, "propose_refund", refund(order, 12500))
    assert again.ok and again.data is not None and again.data["duplicate"] is True
