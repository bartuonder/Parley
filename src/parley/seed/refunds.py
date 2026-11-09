import random
from datetime import datetime, timedelta

from parley.db.enums import InvoiceStatus, OrderStatus, RefundStatus, ShipmentStatus
from parley.db.models import Invoice, Order, Refund
from parley.seed.config import SeedConfig, rng_for

DELIVERED_ORDER_REFUND_RATE = 0.08
LOST_ORDER_REFUND_RATE = 0.6
PAID_INVOICE_REFUND_RATE = 0.04
DUPLICATE_INVOICE_REFUND_RATE = 0.4
PARTIAL_RATE = 0.4
STATUSES = (RefundStatus.PROCESSED, RefundStatus.PENDING_APPROVAL, RefundStatus.REJECTED)
STATUS_WEIGHTS = (85, 7, 8)
ORDER_REASONS = (
    "item arrived damaged",
    "item not as described",
    "changed my mind",
    "wrong size",
    "item stopped working",
)
LOST_REASON = "package lost in transit"
DUPLICATE_REASON = "duplicate charge"
INVOICE_REASONS = ("service not used", "unexpected renewal", "billing error")


def generate_refunds(cfg: SeedConfig, orders: list[Order], invoices: list[Invoice]) -> list[Refund]:
    rng = rng_for(cfg, "refunds")
    refunds: list[Refund] = []
    for order in orders:
        reason = _order_refund_reason(rng, order)
        if reason is not None:
            refund = _order_refund(rng, cfg.now, order, reason, len(refunds) + 1)
            if refund is not None:
                refunds.append(refund)
    duplicates = _duplicate_invoices(invoices)
    for invoice in invoices:
        if invoice.status != InvoiceStatus.PAID:
            continue
        is_duplicate = id(invoice) in duplicates
        rate = DUPLICATE_INVOICE_REFUND_RATE if is_duplicate else PAID_INVOICE_REFUND_RATE
        if rng.random() >= rate:
            continue
        reason = DUPLICATE_REASON if is_duplicate else rng.choice(INVOICE_REASONS)
        refund = _invoice_refund(rng, cfg.now, invoice, reason, len(refunds) + 1)
        if refund is not None:
            refunds.append(refund)
    return refunds


def _order_refund_reason(rng: random.Random, order: Order) -> str | None:
    if order.status == OrderStatus.DELIVERED and rng.random() < DELIVERED_ORDER_REFUND_RATE:
        return rng.choice(ORDER_REASONS)
    lost = any(s.status == ShipmentStatus.LOST for s in order.shipments)
    if lost and rng.random() < LOST_ORDER_REFUND_RATE:
        return LOST_REASON
    return None


def _order_refund(
    rng: random.Random, now: datetime, order: Order, reason: str, n: int
) -> Refund | None:
    created_at = _refund_time(rng, now, order.placed_at)
    if created_at is None:
        return None
    partial = len(order.items) > 1 and rng.random() < PARTIAL_RATE
    amount = order.total_cents
    if partial:
        item = rng.choice(order.items)
        amount = item.quantity * item.unit_price_cents
    status = rng.choices(STATUSES, STATUS_WEIGHTS)[0]
    refund = _refund(rng, order.currency, amount, reason, status, created_at, n)
    refund.order = order
    if status == RefundStatus.PROCESSED:
        order.status = OrderStatus.PARTIALLY_REFUNDED if partial else OrderStatus.REFUNDED
    return refund


def _invoice_refund(
    rng: random.Random, now: datetime, invoice: Invoice, reason: str, n: int
) -> Refund | None:
    created_at = _refund_time(rng, now, invoice.issued_at)
    if created_at is None:
        return None
    status = rng.choices(STATUSES, STATUS_WEIGHTS)[0]
    refund = _refund(rng, invoice.currency, invoice.amount_cents, reason, status, created_at, n)
    refund.invoice = invoice
    if status == RefundStatus.PROCESSED:
        invoice.status = InvoiceStatus.REFUNDED
    return refund


def _refund_time(rng: random.Random, now: datetime, since: datetime) -> datetime | None:
    earliest = since + timedelta(days=3)
    if earliest >= now:
        return None
    return earliest + (now - earliest) * rng.random() * 0.5


def _refund(
    rng: random.Random,
    currency: str,
    amount: int,
    reason: str,
    status: RefundStatus,
    created_at: datetime,
    n: int,
) -> Refund:
    processed_at = None
    if status == RefundStatus.PROCESSED:
        processed_at = created_at + timedelta(hours=rng.randint(1, 72))
    return Refund(
        amount_cents=amount,
        currency=currency,
        reason=reason,
        status=status,
        idempotency_key=f"seed-refund-{n}",
        created_at=created_at,
        processed_at=processed_at,
    )


def _duplicate_invoices(invoices: list[Invoice]) -> set[int]:
    """Ids of paid invoices that repeat a charge for the same subscription and day."""
    seen: set[tuple[int, object, int]] = set()
    duplicates: set[int] = set()
    for invoice in invoices:
        if invoice.status != InvoiceStatus.PAID or invoice.subscription is None:
            continue
        key = (id(invoice.subscription), invoice.issued_at.date(), invoice.amount_cents)
        if key in seen:
            duplicates.add(id(invoice))
        seen.add(key)
    return duplicates
