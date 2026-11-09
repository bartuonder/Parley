import random
from collections import defaultdict
from datetime import UTC, datetime, timedelta

from parley.backend.rules import (
    ANNUAL_COOLING_OFF_DAYS,
    PHYSICAL_WINDOW_DAYS,
    PREMIUM_WINDOW_DAYS,
)
from parley.db.enums import (
    BillingInterval,
    CustomerTier,
    InvoiceStatus,
    ItemCategory,
    RefundStatus,
    ShipmentStatus,
    SubscriptionStatus,
)
from parley.db.models import Customer, Invoice, Order, Subscription, Ticket
from parley.policies.models import PolicyDoc
from parley.seed.config import SeedConfig, rng_for
from parley.seed.refunds import DUPLICATE_REASON, LOST_REASON
from parley.seed.ticket_templates import TEMPLATES, Kind

DENIED_WINDOW_RATE = 0.15
DENIED_FINAL_SALE_RATE = 0.4
LATE_PACKAGE_RATE = 0.8
STUCK_LABEL_RATE = 0.8
WHERE_IS_MY_ORDER_RATE = 0.5
CANCEL_SUBSCRIPTION_RATE = 0.8
FAILED_PAYMENT_RATE = 0.9
OLD_FAILED_PAYMENT_RATE = 0.15
DISPUTE_RATE = 0.8
FAQ_COUNT_WEIGHTS = (10, 25, 30, 20, 15)
FAQ_KINDS = (
    Kind.FAQ_INVOICE_COPY,
    Kind.FAQ_PREMIUM,
    Kind.FAQ_DELIVERY_TIMES,
    Kind.FAQ_PRICING,
)
STUCK_LABEL_MIN_AGE = timedelta(days=5)
HISTORY_START = datetime(2025, 9, 1, tzinfo=UTC)


def generate_tickets(
    cfg: SeedConfig,
    customers: list[Customer],
    orders: list[Order],
    subscriptions: list[Subscription],
    invoices: list[Invoice],
    policies: list[PolicyDoc],
) -> list[Ticket]:
    rng = rng_for(cfg, "tickets")
    builder = _Builder(rng, cfg.now, policies)
    tickets: list[Ticket] = []
    for order in orders:
        tickets += _order_tickets(builder, order)
    for sub in subscriptions:
        tickets += _subscription_tickets(builder, sub)
    for invoice in invoices:
        tickets += _invoice_tickets(builder, invoice)
    for customer in customers:
        tickets += _faq_tickets(builder, customer)
    kept = [t for t in tickets if t.created_at >= HISTORY_START]
    kept.sort(key=lambda t: (t.created_at, t.subject))
    return kept


class _Builder:
    def __init__(self, rng: random.Random, now: datetime, policies: list[PolicyDoc]) -> None:
        self.rng = rng
        self.now = now
        self.versions: dict[str, list[PolicyDoc]] = defaultdict(list)
        for doc in policies:
            self.versions[doc.doc_id].append(doc)

    def between(self, start: datetime, end: datetime) -> datetime:
        end = min(end, self.now - timedelta(hours=1))
        if end <= start:
            return min(start, self.now - timedelta(hours=1))
        return start + (end - start) * self.rng.random()

    def refs(self, policy_ids: tuple[str, ...], at: datetime) -> list[str]:
        day = at.date()
        refs: list[str] = []
        for doc_id in policy_ids:
            live = [
                d
                for d in self.versions[doc_id]
                if d.effective_date <= day and (d.expires_date is None or d.expires_date >= day)
            ]
            if live:
                refs.append(max(live, key=lambda d: d.version).key)
        return refs

    def build(
        self,
        kind: Kind,
        customer: Customer,
        created_at: datetime,
        fields: dict[str, str],
        *,
        order: Order | None = None,
        invoice: Invoice | None = None,
        subscription: Subscription | None = None,
    ) -> Ticket:
        template = TEMPLATES[kind]
        created_at = min(created_at, self.now - timedelta(hours=1))
        resolved_at = min(created_at + timedelta(hours=self.rng.randint(1, 48)), self.now)
        values = {"name": customer.name.split()[0], **fields}
        ticket = Ticket(
            category=template.category,
            outcome=template.outcome,
            subject=self.rng.choice(template.subjects).format_map(values),
            body=self.rng.choice(template.bodies).format_map(values),
            resolution=self.rng.choice(template.replies).format_map(values),
            policy_refs=self.refs(template.policy_ids, created_at),
            created_at=created_at,
            resolved_at=resolved_at,
        )
        ticket.customer = customer
        ticket.order = order
        ticket.invoice = invoice
        ticket.subscription = subscription
        return ticket


def _money(cents: int, currency: str) -> str:
    return f"{cents / 100:.2f} {currency}"


def _order_fields(order: Order) -> dict[str, str]:
    shipment = order.shipments[0] if order.shipments else None
    eta = shipment.estimated_delivery_at if shipment else None
    return {
        "order_id": str(order.id),
        "item": order.items[0].name.lower(),
        "amount": _money(order.total_cents, order.currency),
        "tracking": shipment.tracking_number if shipment else "",
        "carrier": shipment.carrier if shipment else "",
        "eta": eta.strftime("%d %b %Y") if eta else "unknown",
        "reason": "",
        "days": "",
    }


def _order_tickets(b: _Builder, order: Order) -> list[Ticket]:
    customer = order.customer
    fields = _order_fields(order)
    processed = [r for r in order.refunds if r.status == RefundStatus.PROCESSED]
    if processed:
        refund = processed[0]
        kind = Kind.LOST_PACKAGE_REFUND if refund.reason == LOST_REASON else Kind.REFUND_GRANTED
        created = max(
            refund.created_at - timedelta(hours=b.rng.randint(2, 48)),
            order.placed_at + timedelta(hours=1),
        )
        fields |= {"reason": refund.reason, "amount": _money(refund.amount_cents, refund.currency)}
        return [b.build(kind, customer, created, fields, order=order)]

    shipment = order.shipments[0] if order.shipments else None
    if shipment is None:
        return []
    out: list[Ticket] = []
    if shipment.status == ShipmentStatus.DELIVERED and shipment.delivered_at is not None:
        out += _delivered_tickets(b, order, shipment.delivered_at, fields)
        if b.rng.random() < WHERE_IS_MY_ORDER_RATE and shipment.shipped_at is not None:
            created = b.between(shipment.shipped_at, shipment.delivered_at)
            out.append(b.build(Kind.WHERE_IS_MY_ORDER, customer, created, fields, order=order))
    elif shipment.status == ShipmentStatus.IN_TRANSIT and shipment.shipped_at is not None:
        eta = shipment.estimated_delivery_at
        if eta is not None and eta < b.now and b.rng.random() < LATE_PACKAGE_RATE:
            created = b.between(eta, b.now)
            out.append(b.build(Kind.LATE_PACKAGE, customer, created, fields, order=order))
        elif b.rng.random() < WHERE_IS_MY_ORDER_RATE:
            created = b.between(shipment.shipped_at, b.now)
            out.append(b.build(Kind.WHERE_IS_MY_ORDER, customer, created, fields, order=order))
    elif (
        shipment.status == ShipmentStatus.LABEL_CREATED
        and b.now - order.placed_at > STUCK_LABEL_MIN_AGE
        and b.rng.random() < STUCK_LABEL_RATE
    ):
        created = b.between(order.placed_at + STUCK_LABEL_MIN_AGE, b.now)
        out.append(b.build(Kind.STUCK_LABEL, customer, created, fields, order=order))
    return out


def _delivered_tickets(
    b: _Builder, order: Order, delivered_at: datetime, fields: dict[str, str]
) -> list[Ticket]:
    customer = order.customer
    premium = customer.tier == CustomerTier.PREMIUM
    window = PREMIUM_WINDOW_DAYS if premium else PHYSICAL_WINDOW_DAYS
    expiry = delivered_at + timedelta(days=window)
    final_sale = [i for i in order.items if i.category == ItemCategory.FINAL_SALE]
    if expiry + timedelta(days=1) < b.now and b.rng.random() < DENIED_WINDOW_RATE:
        created = b.between(expiry + timedelta(days=1), b.now)
        values = fields | {"days": str(window)}
        return [b.build(Kind.REFUND_DENIED_WINDOW, customer, created, values, order=order)]
    if final_sale and b.rng.random() < DENIED_FINAL_SALE_RATE:
        created = b.between(delivered_at, min(expiry, b.now))
        values = fields | {"item": final_sale[0].name.lower()}
        return [b.build(Kind.REFUND_DENIED_FINAL_SALE, customer, created, values, order=order)]
    return []


def _subscription_tickets(b: _Builder, sub: Subscription) -> list[Ticket]:
    customer = sub.customer
    fields = {"plan": sub.plan.value.capitalize()}
    if sub.status == SubscriptionStatus.CANCELLED and sub.cancelled_at is not None:
        if b.rng.random() < CANCEL_SUBSCRIPTION_RATE:
            created = max(
                sub.cancelled_at - timedelta(hours=b.rng.randint(1, 12)),
                sub.started_at + timedelta(hours=1),
            )
            return [b.build(Kind.CANCEL_SUBSCRIPTION, customer, created, fields, subscription=sub)]
    elif sub.cancel_at_period_end:
        created = b.between(sub.started_at + timedelta(days=1), b.now)
        return [b.build(Kind.CANCEL_SUBSCRIPTION, customer, created, fields, subscription=sub)]
    elif sub.status == SubscriptionStatus.PAST_DUE and b.rng.random() < FAILED_PAYMENT_RATE:
        failed = [i for i in sub.invoices if i.status == InvoiceStatus.FAILED]
        if failed:
            invoice = failed[-1]
            created = invoice.issued_at + timedelta(days=1)
            values = fields | {"invoice_id": str(invoice.id)}
            return [
                b.build(
                    Kind.FAILED_PAYMENT,
                    customer,
                    created,
                    values,
                    invoice=invoice,
                    subscription=sub,
                )
            ]
    return []


def _invoice_tickets(b: _Builder, invoice: Invoice) -> list[Ticket]:
    customer = invoice.customer
    sub = invoice.subscription
    fields = {
        "invoice_id": str(invoice.id),
        "amount": _money(invoice.amount_cents, invoice.currency),
        "plan": sub.plan.value.capitalize() if sub else "",
    }
    refund = next((r for r in invoice.refunds if r.status == RefundStatus.PROCESSED), None)
    if refund is not None:
        created = max(
            refund.created_at - timedelta(hours=b.rng.randint(2, 48)),
            invoice.issued_at + timedelta(hours=1),
        )
        if refund.reason == DUPLICATE_REASON:
            return [
                b.build(Kind.DUPLICATE_CHARGE_REFUND, customer, created, fields, invoice=invoice)
            ]
        cooling_off = timedelta(days=ANNUAL_COOLING_OFF_DAYS)
        annual = sub is not None and sub.interval == BillingInterval.ANNUAL
        if annual and refund.created_at - invoice.issued_at <= cooling_off:
            return [b.build(Kind.ANNUAL_RENEWAL_REFUND, customer, created, fields, invoice=invoice)]
        return []
    if invoice.status == InvoiceStatus.DISPUTED and b.rng.random() < DISPUTE_RATE:
        created = b.between(invoice.issued_at + timedelta(days=1), b.now)
        return [b.build(Kind.DISPUTED_INVOICE, customer, created, fields, invoice=invoice)]
    past_due = sub is not None and sub.status == SubscriptionStatus.PAST_DUE
    old_failure = invoice.status == InvoiceStatus.FAILED and not past_due
    if old_failure and b.rng.random() < OLD_FAILED_PAYMENT_RATE:
        created = b.between(invoice.issued_at, invoice.issued_at + timedelta(days=3))
        return [b.build(Kind.FAILED_PAYMENT, customer, created, fields, invoice=invoice)]
    return []


def _faq_tickets(b: _Builder, customer: Customer) -> list[Ticket]:
    count = b.rng.choices(range(len(FAQ_COUNT_WEIGHTS)), FAQ_COUNT_WEIGHTS)[0]
    tickets: list[Ticket] = []
    for _ in range(count):
        kind = b.rng.choice(FAQ_KINDS)
        created = b.between(customer.created_at, b.now)
        tickets.append(b.build(kind, customer, created, {}))
    return tickets
