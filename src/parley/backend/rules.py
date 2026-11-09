from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum

from parley.db.enums import (
    BillingInterval,
    CustomerTier,
    InvoiceStatus,
    ItemCategory,
    OrderStatus,
    RefundStatus,
    ShipmentStatus,
)
from parley.db.models import Invoice, Order, Shipment

PHYSICAL_WINDOW_DAYS = 30
PREMIUM_WINDOW_DAYS = 45
DIGITAL_WINDOW_DAYS = 7
LOST_GRACE_DAYS = 10
ANNUAL_COOLING_OFF_DAYS = 14
APPROVAL_THRESHOLD_CENTS = 20_000

ACTIVE_REFUND_STATUSES = (RefundStatus.PROCESSED, RefundStatus.PENDING_APPROVAL)


class EligibilityCode(StrEnum):
    ELIGIBLE = "eligible"
    ELIGIBLE_LOST_SHIPMENT = "eligible_lost_shipment"
    ELIGIBLE_DUPLICATE_CHARGE = "eligible_duplicate_charge"
    ELIGIBLE_ANNUAL_COOLING_OFF = "eligible_annual_cooling_off"
    ORDER_CANCELLED = "order_cancelled"
    NOT_DELIVERED = "not_delivered"
    WINDOW_EXPIRED = "window_expired"
    FINAL_SALE = "final_sale"
    ALREADY_REFUNDED = "already_refunded"
    INVOICE_NOT_PAID = "invoice_not_paid"
    INVOICE_DISPUTED = "invoice_disputed"
    NOT_REFUNDABLE = "not_refundable"


@dataclass(frozen=True)
class Eligibility:
    eligible: bool
    code: EligibilityCode
    max_refund_cents: int = 0


def requires_approval(amount_cents: int) -> bool:
    return amount_cents > APPROVAL_THRESHOLD_CENTS


def order_refund_eligibility(order: Order, now: datetime) -> Eligibility:
    if order.status == OrderStatus.CANCELLED:
        return _deny(EligibilityCode.ORDER_CANCELLED)

    reserved = sum(r.amount_cents for r in order.refunds if r.status in ACTIVE_REFUND_STATUSES)
    shipment = _latest_shipment(order)

    if shipment is not None and _is_lost(shipment, now):
        remaining = order.total_cents - reserved
        if remaining <= 0:
            return _deny(EligibilityCode.ALREADY_REFUNDED)
        return _grant(EligibilityCode.ELIGIBLE_LOST_SHIPMENT, remaining)

    if shipment is not None and shipment.status != ShipmentStatus.DELIVERED:
        return _deny(EligibilityCode.NOT_DELIVERED)
    if shipment is None and order.items and _has_physical(order):
        return _deny(EligibilityCode.NOT_DELIVERED)

    eligible_total, code = _refundable_item_total(order, shipment, now)
    if eligible_total == 0:
        return _deny(code)
    remaining = eligible_total - reserved
    if remaining <= 0:
        return _deny(EligibilityCode.ALREADY_REFUNDED)
    return _grant(EligibilityCode.ELIGIBLE, remaining)


def invoice_refund_eligibility(
    invoice: Invoice, has_earlier_duplicate: bool, now: datetime
) -> Eligibility:
    if invoice.status == InvoiceStatus.DISPUTED:
        return _deny(EligibilityCode.INVOICE_DISPUTED)
    if invoice.status == InvoiceStatus.REFUNDED:
        return _deny(EligibilityCode.ALREADY_REFUNDED)
    if invoice.status != InvoiceStatus.PAID:
        return _deny(EligibilityCode.INVOICE_NOT_PAID)

    reserved = sum(r.amount_cents for r in invoice.refunds if r.status in ACTIVE_REFUND_STATUSES)
    remaining = invoice.amount_cents - reserved
    if remaining <= 0:
        return _deny(EligibilityCode.ALREADY_REFUNDED)

    if has_earlier_duplicate:
        return _grant(EligibilityCode.ELIGIBLE_DUPLICATE_CHARGE, remaining)

    sub = invoice.subscription
    cooling_off = timedelta(days=ANNUAL_COOLING_OFF_DAYS)
    if (
        sub is not None
        and sub.interval == BillingInterval.ANNUAL
        and now - invoice.issued_at <= cooling_off
    ):
        return _grant(EligibilityCode.ELIGIBLE_ANNUAL_COOLING_OFF, remaining)
    return _deny(EligibilityCode.NOT_REFUNDABLE)


def _grant(code: EligibilityCode, amount_cents: int) -> Eligibility:
    return Eligibility(True, code, amount_cents)


def _deny(code: EligibilityCode) -> Eligibility:
    return Eligibility(False, code, 0)


def _latest_shipment(order: Order) -> Shipment | None:
    if not order.shipments:
        return None
    return max(order.shipments, key=lambda s: s.id or 0)


def _is_lost(shipment: Shipment, now: datetime) -> bool:
    if shipment.status in (ShipmentStatus.LOST, ShipmentStatus.RETURNED):
        return True
    eta = shipment.estimated_delivery_at
    overdue = timedelta(days=LOST_GRACE_DAYS)
    return shipment.status == ShipmentStatus.IN_TRANSIT and eta is not None and now - eta > overdue


def _has_physical(order: Order) -> bool:
    return any(i.category != ItemCategory.DIGITAL for i in order.items)


def _window_days(order: Order) -> int:
    return (
        PREMIUM_WINDOW_DAYS if order.customer.tier == CustomerTier.PREMIUM else PHYSICAL_WINDOW_DAYS
    )


def _refundable_item_total(
    order: Order, shipment: Shipment | None, now: datetime
) -> tuple[int, EligibilityCode]:
    """Sum of items still inside their return window, or the reason none are."""
    total = 0
    saw_non_final = False
    for item in order.items:
        if item.category == ItemCategory.FINAL_SALE:
            continue
        saw_non_final = True
        if item.category == ItemCategory.DIGITAL:
            start, days = order.placed_at, DIGITAL_WINDOW_DAYS
        else:
            start = shipment.delivered_at if shipment and shipment.delivered_at else order.placed_at
            days = _window_days(order)
        if now - start <= timedelta(days=days):
            total += item.quantity * item.unit_price_cents
    if total > 0:
        return total, EligibilityCode.ELIGIBLE
    code = EligibilityCode.WINDOW_EXPIRED if saw_non_final else EligibilityCode.FINAL_SALE
    return 0, code
