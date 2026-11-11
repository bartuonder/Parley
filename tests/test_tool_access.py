import pytest
from sqlalchemy.orm import Session

from parley.backend.services import Backend, NotFoundError
from parley.tools.access import (
    AccessDeniedError,
    own_invoice,
    own_order,
    own_shipment,
    own_subscription,
)
from parley.tools.context import ToolContext
from tests.factories import NOW, make_customer, make_order, make_shipment, make_subscription


@pytest.fixture
def ctx(session: Session) -> ToolContext:
    sender = make_customer(session, "ada@example.com")
    return ToolContext(Backend(session, lambda: NOW), sender.id, "T-1")


def test_sender_can_reach_own_records(session: Session, ctx: ToolContext) -> None:
    sender = ctx.backend.get_customer(ctx.customer_id)
    order = make_order(session, sender)
    sub = make_subscription(session, sender)
    shipment = make_shipment(session, order, tracking="TRK-OWN")
    assert own_order(ctx, order.id).id == order.id
    assert own_subscription(ctx, sub.id).id == sub.id
    assert own_shipment(ctx, "TRK-OWN").id == shipment.id


def test_other_customers_records_are_denied(session: Session, ctx: ToolContext) -> None:
    other = make_customer(session, "bob@example.com")
    order = make_order(session, other)
    sub = make_subscription(session, other)
    make_shipment(session, order, tracking="TRK-OTHER")
    with pytest.raises(AccessDeniedError):
        own_order(ctx, order.id)
    with pytest.raises(AccessDeniedError):
        own_subscription(ctx, sub.id)
    with pytest.raises(AccessDeniedError):
        own_shipment(ctx, "TRK-OTHER")


def test_missing_records_still_raise_not_found(ctx: ToolContext) -> None:
    with pytest.raises(NotFoundError):
        own_order(ctx, 999_999)
    with pytest.raises(NotFoundError):
        own_invoice(ctx, 999_999)
