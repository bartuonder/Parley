from datetime import UTC, datetime, timedelta

import pytest

from parley.backend.rules import (
    APPROVAL_THRESHOLD_CENTS,
    EligibilityCode,
    invoice_refund_eligibility,
    order_refund_eligibility,
    requires_approval,
)
from parley.db.enums import (
    BillingInterval,
    CustomerTier,
    InvoiceStatus,
    ItemCategory,
    OrderStatus,
    RefundStatus,
    ShipmentStatus,
    SubscriptionPlan,
    SubscriptionStatus,
)
from parley.db.models import Customer, Invoice, Order, OrderItem, Refund, Shipment, Subscription

NOW = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)


def days_ago(n: float) -> datetime:
    return NOW - timedelta(days=n)


def build_order(
    *,
    categories: tuple[ItemCategory, ...] = (ItemCategory.PHYSICAL,),
    tier: CustomerTier = CustomerTier.STANDARD,
    status: OrderStatus = OrderStatus.DELIVERED,
    shipment_status: ShipmentStatus | None = ShipmentStatus.DELIVERED,
    delivered_days_ago: float = 5,
    eta_days_ago: float | None = None,
    placed_days_ago: float = 10,
) -> Order:
    customer = Customer(email="a@example.com", name="A", country="US", tier=tier, created_at=NOW)
    items = [
        OrderItem(sku=f"S{i}", name="x", category=c, quantity=1, unit_price_cents=1000)
        for i, c in enumerate(categories)
    ]
    order = Order(
        status=status,
        currency="USD",
        total_cents=1000 * len(items),
        placed_at=days_ago(placed_days_ago),
        customer=customer,
        items=items,
        shipments=[],
        refunds=[],
    )
    if shipment_status is not None:
        delivered = shipment_status == ShipmentStatus.DELIVERED
        order.shipments.append(
            Shipment(
                carrier="DHL",
                tracking_number="T1",
                status=shipment_status,
                shipped_at=days_ago(placed_days_ago),
                estimated_delivery_at=days_ago(eta_days_ago) if eta_days_ago is not None else None,
                delivered_at=days_ago(delivered_days_ago) if delivered else None,
            )
        )
    return order


def add_refund(order: Order, amount: int, status: RefundStatus = RefundStatus.PROCESSED) -> None:
    order.refunds.append(
        Refund(
            amount_cents=amount,
            currency="USD",
            reason="r",
            status=status,
            idempotency_key=f"k{len(order.refunds)}",
            created_at=NOW,
        )
    )


def test_delivered_inside_window_is_eligible_for_full_total() -> None:
    result = order_refund_eligibility(build_order(delivered_days_ago=10), NOW)
    assert result.eligible
    assert result.code == EligibilityCode.ELIGIBLE
    assert result.max_refund_cents == 1000


def test_standard_window_boundary() -> None:
    inside = order_refund_eligibility(build_order(delivered_days_ago=30), NOW)
    outside = order_refund_eligibility(build_order(delivered_days_ago=31), NOW)
    assert inside.eligible
    assert outside.code == EligibilityCode.WINDOW_EXPIRED


def test_premium_window_is_longer() -> None:
    premium = CustomerTier.PREMIUM
    assert order_refund_eligibility(build_order(tier=premium, delivered_days_ago=40), NOW).eligible
    expired = order_refund_eligibility(build_order(tier=premium, delivered_days_ago=46), NOW)
    assert expired.code == EligibilityCode.WINDOW_EXPIRED


def test_final_sale_is_never_refundable() -> None:
    order = build_order(categories=(ItemCategory.FINAL_SALE,))
    assert order_refund_eligibility(order, NOW).code == EligibilityCode.FINAL_SALE


def test_mixed_order_excludes_final_sale_items() -> None:
    order = build_order(categories=(ItemCategory.PHYSICAL, ItemCategory.FINAL_SALE))
    result = order_refund_eligibility(order, NOW)
    assert result.eligible
    assert result.max_refund_cents == 1000


def test_digital_window_is_seven_days_from_purchase() -> None:
    def digital(placed: float) -> Order:
        return build_order(
            categories=(ItemCategory.DIGITAL,), shipment_status=None, placed_days_ago=placed
        )

    assert order_refund_eligibility(digital(7), NOW).eligible
    assert order_refund_eligibility(digital(8), NOW).code == EligibilityCode.WINDOW_EXPIRED


def test_cancelled_order_is_denied() -> None:
    order = build_order(status=OrderStatus.CANCELLED, shipment_status=None)
    assert order_refund_eligibility(order, NOW).code == EligibilityCode.ORDER_CANCELLED


def test_in_transit_within_grace_is_not_delivered() -> None:
    order = build_order(
        status=OrderStatus.SHIPPED, shipment_status=ShipmentStatus.IN_TRANSIT, eta_days_ago=3
    )
    assert order_refund_eligibility(order, NOW).code == EligibilityCode.NOT_DELIVERED


def test_in_transit_far_past_eta_counts_as_lost() -> None:
    order = build_order(
        status=OrderStatus.SHIPPED, shipment_status=ShipmentStatus.IN_TRANSIT, eta_days_ago=11
    )
    result = order_refund_eligibility(order, NOW)
    assert result.code == EligibilityCode.ELIGIBLE_LOST_SHIPMENT
    assert result.max_refund_cents == 1000


@pytest.mark.parametrize("status", [ShipmentStatus.LOST, ShipmentStatus.RETURNED])
def test_lost_or_returned_shipment_is_eligible_even_outside_window(status: ShipmentStatus) -> None:
    order = build_order(status=OrderStatus.SHIPPED, shipment_status=status, placed_days_ago=90)
    assert order_refund_eligibility(order, NOW).code == EligibilityCode.ELIGIBLE_LOST_SHIPMENT


def test_partial_refund_reduces_remaining_amount() -> None:
    order = build_order(categories=(ItemCategory.PHYSICAL, ItemCategory.PHYSICAL))
    add_refund(order, 500)
    assert order_refund_eligibility(order, NOW).max_refund_cents == 1500


def test_fully_refunded_order_is_denied() -> None:
    order = build_order()
    add_refund(order, 1000)
    assert order_refund_eligibility(order, NOW).code == EligibilityCode.ALREADY_REFUNDED


def test_pending_refund_reserves_amount() -> None:
    order = build_order()
    add_refund(order, 1000, RefundStatus.PENDING_APPROVAL)
    assert order_refund_eligibility(order, NOW).code == EligibilityCode.ALREADY_REFUNDED


def test_rejected_refund_does_not_reserve_amount() -> None:
    order = build_order()
    add_refund(order, 1000, RefundStatus.REJECTED)
    assert order_refund_eligibility(order, NOW).eligible


def build_invoice(
    *,
    status: InvoiceStatus = InvoiceStatus.PAID,
    interval: BillingInterval = BillingInterval.MONTHLY,
    issued_days_ago: float = 3,
) -> Invoice:
    sub = Subscription(
        plan=SubscriptionPlan.PRO,
        interval=interval,
        status=SubscriptionStatus.ACTIVE,
        price_cents=1900,
        currency="USD",
        started_at=days_ago(100),
        current_period_end=NOW,
    )
    return Invoice(
        status=status,
        amount_cents=1900,
        currency="USD",
        issued_at=days_ago(issued_days_ago),
        subscription=sub,
        refunds=[],
    )


def test_monthly_invoice_is_not_refundable() -> None:
    result = invoice_refund_eligibility(build_invoice(), False, NOW)
    assert result.code == EligibilityCode.NOT_REFUNDABLE


def test_duplicate_charge_is_refundable_in_full() -> None:
    result = invoice_refund_eligibility(build_invoice(), True, NOW)
    assert result.code == EligibilityCode.ELIGIBLE_DUPLICATE_CHARGE
    assert result.max_refund_cents == 1900


def test_annual_cooling_off_boundary() -> None:
    annual = BillingInterval.ANNUAL
    inside = invoice_refund_eligibility(
        build_invoice(interval=annual, issued_days_ago=14), False, NOW
    )
    outside = invoice_refund_eligibility(
        build_invoice(interval=annual, issued_days_ago=15), False, NOW
    )
    assert inside.code == EligibilityCode.ELIGIBLE_ANNUAL_COOLING_OFF
    assert outside.code == EligibilityCode.NOT_REFUNDABLE


@pytest.mark.parametrize(
    ("status", "code"),
    [
        (InvoiceStatus.FAILED, EligibilityCode.INVOICE_NOT_PAID),
        (InvoiceStatus.DISPUTED, EligibilityCode.INVOICE_DISPUTED),
        (InvoiceStatus.REFUNDED, EligibilityCode.ALREADY_REFUNDED),
    ],
)
def test_non_paid_invoice_states(status: InvoiceStatus, code: EligibilityCode) -> None:
    assert invoice_refund_eligibility(build_invoice(status=status), True, NOW).code == code


def test_approval_threshold_boundary() -> None:
    assert not requires_approval(APPROVAL_THRESHOLD_CENTS)
    assert requires_approval(APPROVAL_THRESHOLD_CENTS + 1)
