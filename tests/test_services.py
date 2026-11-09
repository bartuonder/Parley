from datetime import timedelta

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from parley.backend.rules import APPROVAL_THRESHOLD_CENTS
from parley.backend.services import (
    Backend,
    IdempotencyConflictError,
    InvalidRequestError,
    NotEligibleError,
    NotFoundError,
    RefundTarget,
)
from parley.db.enums import (
    InvoiceStatus,
    OrderStatus,
    RefundStatus,
    ShipmentStatus,
    SubscriptionStatus,
)
from parley.db.models import Invoice, Order, Refund
from tests.factories import (
    NOW,
    make_customer,
    make_item,
    make_order,
    make_shipment,
    make_subscription,
)

CLOCK = NOW + timedelta(days=10)


@pytest.fixture
def backend(session: Session) -> Backend:
    return Backend(session, lambda: CLOCK)


def delivered_order(session: Session, price: int = 5000) -> Order:
    order = make_order(session, make_customer(session), total_cents=price)
    make_item(session, order, unit_price_cents=price)
    make_shipment(session, order, status=ShipmentStatus.DELIVERED, delivered_at=NOW)
    order.status = OrderStatus.DELIVERED
    session.flush()
    return order


def refund_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Refund)) or 0


def test_find_customer_by_email_is_case_insensitive(session: Session, backend: Backend) -> None:
    customer = make_customer(session, "ada@example.com")
    assert backend.find_customer_by_email("ADA@Example.com").id == customer.id


def test_unknown_entities_raise_not_found(backend: Backend) -> None:
    with pytest.raises(NotFoundError):
        backend.get_order(999)
    with pytest.raises(NotFoundError):
        backend.find_customer_by_email("nobody@example.com")
    with pytest.raises(NotFoundError):
        backend.get_shipment_by_tracking("nope")


def test_full_refund_is_processed_and_marks_order_refunded(
    session: Session, backend: Backend
) -> None:
    order = delivered_order(session)
    refund, created = backend.issue_refund(RefundTarget.ORDER, order.id, 5000, "damaged", "k1")
    assert created
    assert refund.status == RefundStatus.PROCESSED
    assert refund.processed_at == CLOCK
    assert order.status == OrderStatus.REFUNDED


def test_partial_refund_marks_order_partially_refunded(session: Session, backend: Backend) -> None:
    order = delivered_order(session)
    backend.issue_refund(RefundTarget.ORDER, order.id, 2000, "one item", "k1")
    assert order.status == OrderStatus.PARTIALLY_REFUNDED
    assert backend.check_order_refund(order.id).max_refund_cents == 3000


def test_amount_above_refundable_maximum_is_rejected(session: Session, backend: Backend) -> None:
    order = delivered_order(session)
    with pytest.raises(InvalidRequestError):
        backend.issue_refund(RefundTarget.ORDER, order.id, 5001, "too much", "k1")
    assert refund_count(session) == 0


def test_non_positive_amount_is_rejected(session: Session, backend: Backend) -> None:
    order = delivered_order(session)
    with pytest.raises(InvalidRequestError):
        backend.issue_refund(RefundTarget.ORDER, order.id, 0, "zero", "k1")


def test_ineligible_order_raises_with_reason_code(session: Session, backend: Backend) -> None:
    order = delivered_order(session)
    late = Backend(session, lambda: NOW + timedelta(days=60))
    with pytest.raises(NotEligibleError) as exc:
        late.issue_refund(RefundTarget.ORDER, order.id, 5000, "late", "k1")
    assert exc.value.code == "window_expired"


def test_same_idempotency_key_replays_without_a_second_refund(
    session: Session, backend: Backend
) -> None:
    order = delivered_order(session)
    first, created_first = backend.issue_refund(RefundTarget.ORDER, order.id, 2000, "r", "k1")
    second, created_second = backend.issue_refund(RefundTarget.ORDER, order.id, 2000, "r", "k1")
    assert created_first and not created_second
    assert first.id == second.id
    assert refund_count(session) == 1


def test_idempotency_key_reused_for_different_request_conflicts(
    session: Session, backend: Backend
) -> None:
    order = delivered_order(session)
    backend.issue_refund(RefundTarget.ORDER, order.id, 2000, "r", "k1")
    with pytest.raises(IdempotencyConflictError):
        backend.issue_refund(RefundTarget.ORDER, order.id, 1000, "r", "k1")


def test_pending_refund_reserves_amount_against_a_second_refund(
    session: Session, backend: Backend
) -> None:
    order = delivered_order(session, price=APPROVAL_THRESHOLD_CENTS + 1)
    refund, _ = backend.issue_refund(
        RefundTarget.ORDER, order.id, APPROVAL_THRESHOLD_CENTS + 1, "big", "k1"
    )
    assert refund.status == RefundStatus.PENDING_APPROVAL
    assert refund.processed_at is None
    assert order.status == OrderStatus.DELIVERED
    with pytest.raises(NotEligibleError):
        backend.issue_refund(RefundTarget.ORDER, order.id, 100, "again", "k2")


def test_approving_pending_refund_processes_it(session: Session, backend: Backend) -> None:
    order = delivered_order(session, price=APPROVAL_THRESHOLD_CENTS + 1)
    refund, _ = backend.issue_refund(
        RefundTarget.ORDER, order.id, APPROVAL_THRESHOLD_CENTS + 1, "big", "k1"
    )
    resolved = backend.resolve_refund(refund.id, approve=True)
    assert resolved.status == RefundStatus.PROCESSED
    assert resolved.processed_at == CLOCK
    assert order.status == OrderStatus.REFUNDED


def test_rejecting_pending_refund_frees_the_amount(session: Session, backend: Backend) -> None:
    order = delivered_order(session, price=APPROVAL_THRESHOLD_CENTS + 1)
    refund, _ = backend.issue_refund(
        RefundTarget.ORDER, order.id, APPROVAL_THRESHOLD_CENTS + 1, "big", "k1"
    )
    assert backend.resolve_refund(refund.id, approve=False).status == RefundStatus.REJECTED
    assert order.status == OrderStatus.DELIVERED
    assert backend.check_order_refund(order.id).eligible


def test_resolving_a_processed_refund_is_invalid(session: Session, backend: Backend) -> None:
    order = delivered_order(session)
    refund, _ = backend.issue_refund(RefundTarget.ORDER, order.id, 5000, "r", "k1")
    with pytest.raises(InvalidRequestError):
        backend.resolve_refund(refund.id, approve=True)


def paid_invoice(session: Session, sub_id: int, customer_id: int, minutes: int = 0) -> Invoice:
    invoice = Invoice(
        customer_id=customer_id,
        subscription_id=sub_id,
        status=InvoiceStatus.PAID,
        amount_cents=1900,
        currency="USD",
        issued_at=NOW + timedelta(minutes=minutes),
    )
    session.add(invoice)
    session.flush()
    return invoice


def test_only_the_later_duplicate_invoice_is_refundable(session: Session, backend: Backend) -> None:
    customer = make_customer(session)
    sub = make_subscription(session, customer)
    original = paid_invoice(session, sub.id, customer.id)
    duplicate = paid_invoice(session, sub.id, customer.id, minutes=2)

    assert not backend.check_invoice_refund(original.id).eligible
    assert backend.check_invoice_refund(duplicate.id).code == "eligible_duplicate_charge"

    refund, _ = backend.issue_refund(RefundTarget.INVOICE, duplicate.id, 1900, "dup", "k1")
    assert refund.status == RefundStatus.PROCESSED
    assert duplicate.status == InvoiceStatus.REFUNDED


def test_cancel_subscription_schedules_cancellation_and_is_repeatable(
    session: Session, backend: Backend
) -> None:
    sub = make_subscription(session, make_customer(session))
    backend.cancel_subscription(sub.id)
    backend.cancel_subscription(sub.id)
    assert sub.cancel_at_period_end
    assert sub.status == SubscriptionStatus.ACTIVE


def test_cancelling_a_cancelled_subscription_is_invalid(session: Session, backend: Backend) -> None:
    sub = make_subscription(session, make_customer(session))
    sub.status = SubscriptionStatus.CANCELLED
    with pytest.raises(InvalidRequestError):
        backend.cancel_subscription(sub.id)
