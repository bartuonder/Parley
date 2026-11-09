import pytest
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from parley.db.enums import InvoiceStatus, RefundStatus
from parley.db.models import Invoice, Refund
from tests.factories import (
    NOW,
    make_customer,
    make_item,
    make_order,
    make_shipment,
    make_subscription,
)

EXPECTED_TABLES = {
    "customers",
    "orders",
    "order_items",
    "shipments",
    "subscriptions",
    "invoices",
    "refunds",
}


def make_refund(**overrides: object) -> Refund:
    fields: dict[str, object] = {
        "amount_cents": 1000,
        "currency": "USD",
        "reason": "damaged",
        "status": RefundStatus.PENDING_APPROVAL,
        "idempotency_key": "key-1",
        "created_at": NOW,
    }
    fields.update(overrides)
    return Refund(**fields)


def test_expected_tables_exist(session: Session) -> None:
    tables = set(inspect(session.connection()).get_table_names())
    assert tables >= EXPECTED_TABLES


def test_order_graph_round_trip(session: Session) -> None:
    customer = make_customer(session)
    order = make_order(session, customer)
    make_item(session, order)
    make_shipment(session, order)
    make_subscription(session, customer)
    session.expire_all()

    loaded = session.get(type(order), order.id)
    assert loaded is not None
    assert loaded.customer.email == "ada@example.com"
    assert len(loaded.items) == 1
    assert loaded.shipments[0].tracking_number == "TRK-1"
    assert customer.subscriptions[0].price_cents == 1900


def test_refund_requires_exactly_one_target(session: Session) -> None:
    order = make_order(session, make_customer(session))
    invoice = Invoice(
        customer_id=order.customer_id,
        status=InvoiceStatus.PAID,
        amount_cents=1900,
        currency="USD",
        issued_at=NOW,
    )
    session.add(invoice)
    session.flush()

    session.add(make_refund(order_id=order.id, invoice_id=invoice.id))
    with pytest.raises(IntegrityError):
        session.flush()


def test_refund_without_target_is_rejected(session: Session) -> None:
    session.add(make_refund())
    with pytest.raises(IntegrityError):
        session.flush()


def test_refund_idempotency_key_is_unique(session: Session) -> None:
    order = make_order(session, make_customer(session))
    session.add(make_refund(order_id=order.id))
    session.flush()
    session.add(make_refund(order_id=order.id))
    with pytest.raises(IntegrityError):
        session.flush()


def test_negative_order_total_is_rejected(session: Session) -> None:
    customer = make_customer(session)
    with pytest.raises(IntegrityError):
        make_order(session, customer, total_cents=-1)


def test_invalid_enum_value_is_rejected(session: Session) -> None:
    customer = make_customer(session)
    with pytest.raises(IntegrityError):
        session.execute(
            text("UPDATE customers SET tier = 'vip' WHERE id = :id"), {"id": customer.id}
        )
