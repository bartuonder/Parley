import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from parley.db.enums import RefundStatus
from parley.db.models import (
    Customer,
    Invoice,
    Order,
    OrderItem,
    Refund,
    Shipment,
    Subscription,
)
from parley.evals.schema import CustomerSpec, Scenario
from parley.memory.tables import CustomerMemoryRow
from parley.seed.config import REFERENCE_NOW


@dataclass
class WorldIndex:
    customers: dict[str, int] = field(default_factory=dict)
    orders: dict[str, int] = field(default_factory=dict)
    invoices: dict[str, int] = field(default_factory=dict)
    subscriptions: dict[str, int] = field(default_factory=dict)
    refunds: dict[str, int] = field(default_factory=dict)


def _ago(days: float | None, now: datetime) -> datetime | None:
    return None if days is None else now - timedelta(days=days)


def _from_now(days: float | None, now: datetime) -> datetime | None:
    return None if days is None else now + timedelta(days=days)


def build_world(session: Session, scenario: Scenario, now: datetime = REFERENCE_NOW) -> WorldIndex:
    """Insert the scenario's fixture rows and return alias-to-id maps."""
    index = WorldIndex()
    objects: dict[str, Order | Invoice | Subscription] = {}
    for spec in scenario.world:
        customer = _customer(spec, now)
        session.add(customer)
        _add_orders(session, scenario.id, spec, customer, objects, now)
        _add_subscriptions(session, spec, customer, objects, now)
        _add_invoices(session, spec, customer, objects, now)
        session.flush()
        index.customers[spec.alias] = customer.id
        _add_refunds(session, scenario.id, spec, objects, now)
    session.flush()
    for obj_alias, obj in objects.items():
        _register(index, obj_alias, obj)
    _index_refunds(session, scenario, index)
    _add_memory(session, scenario, index, now)
    return index


def _customer(spec: CustomerSpec, now: datetime) -> Customer:
    return Customer(
        email=spec.email,
        name=spec.name,
        country=spec.country,
        tier=spec.tier,
        created_at=now - timedelta(days=400),
    )


def _add_orders(
    session: Session,
    scenario_id: str,
    spec: CustomerSpec,
    customer: Customer,
    objects: dict[str, Order | Invoice | Subscription],
    now: datetime,
) -> None:
    for o in spec.orders:
        order = Order(
            status=o.status,
            currency="USD",
            total_cents=sum(i.quantity * i.unit_price_cents for i in o.items),
            placed_at=now - timedelta(days=o.placed_days_ago),
            customer=customer,
            items=[OrderItem(**i.model_dump()) for i in o.items],
        )
        if o.shipment is not None:
            s = o.shipment
            order.shipments.append(
                Shipment(
                    carrier=s.carrier,
                    tracking_number=f"TRK-{scenario_id}-{o.alias}",
                    status=s.status,
                    shipped_at=_ago(s.shipped_days_ago, now),
                    estimated_delivery_at=_from_now(s.eta_days_from_now, now),
                    delivered_at=_ago(s.delivered_days_ago, now),
                )
            )
        session.add(order)
        objects[o.alias] = order


def _add_subscriptions(
    session: Session,
    spec: CustomerSpec,
    customer: Customer,
    objects: dict[str, Order | Invoice | Subscription],
    now: datetime,
) -> None:
    for s in spec.subscriptions:
        sub = Subscription(
            customer=customer,
            plan=s.plan,
            interval=s.interval,
            status=s.status,
            price_cents=s.price_cents,
            currency="USD",
            started_at=now - timedelta(days=s.started_days_ago),
            current_period_end=now + timedelta(days=s.period_end_days_from_now),
            cancel_at_period_end=s.cancel_at_period_end,
        )
        session.add(sub)
        objects[s.alias] = sub


def _add_invoices(
    session: Session,
    spec: CustomerSpec,
    customer: Customer,
    objects: dict[str, Order | Invoice | Subscription],
    now: datetime,
) -> None:
    for i in spec.invoices:
        sub = objects[i.subscription] if i.subscription else None
        invoice = Invoice(
            customer=customer,
            subscription=sub if isinstance(sub, Subscription) else None,
            status=i.status,
            amount_cents=i.amount_cents,
            currency="USD",
            issued_at=now - timedelta(days=i.issued_days_ago),
        )
        session.add(invoice)
        objects[i.alias] = invoice


def _add_refunds(
    session: Session,
    scenario_id: str,
    spec: CustomerSpec,
    objects: dict[str, Order | Invoice | Subscription],
    now: datetime,
) -> None:
    for r in spec.refunds:
        target = objects[r.order or r.invoice or ""]
        created = now - timedelta(days=r.created_days_ago)
        refund = Refund(
            order=target if isinstance(target, Order) else None,
            invoice=target if isinstance(target, Invoice) else None,
            amount_cents=r.amount_cents,
            currency="USD",
            reason=r.reason,
            status=r.status,
            idempotency_key=f"{scenario_id}-seed-{r.alias}",
            created_at=created,
            processed_at=created if r.status == RefundStatus.PROCESSED else None,
        )
        session.add(refund)


def _register(index: WorldIndex, alias: str, obj: Order | Invoice | Subscription) -> None:
    if isinstance(obj, Order):
        index.orders[alias] = obj.id
    elif isinstance(obj, Invoice):
        index.invoices[alias] = obj.id
    else:
        index.subscriptions[alias] = obj.id


def _index_refunds(session: Session, scenario: Scenario, index: WorldIndex) -> None:
    for spec in scenario.world:
        for r in spec.refunds:
            key = f"{scenario.id}-seed-{r.alias}"
            stmt = select(Refund.id).where(Refund.idempotency_key == key)
            index.refunds[r.alias] = session.execute(stmt).scalar_one()


def _add_memory(session: Session, scenario: Scenario, index: WorldIndex, now: datetime) -> None:
    for spec in scenario.memory:
        session.add(
            CustomerMemoryRow(
                customer_id=index.customers[spec.customer],
                kind=spec.kind,
                content=render_text(spec.content, index),
                ticket_id=spec.ticket_id,
                created_at=now - timedelta(days=spec.days_ago),
            )
        )
    session.flush()


def render_text(text: str, index: WorldIndex) -> str:
    """Replace {alias} placeholders with the database ids of the built world."""
    ids = {
        **index.customers,
        **index.orders,
        **index.invoices,
        **index.subscriptions,
        **index.refunds,
    }
    return re.sub(r"\{(\w+)\}", lambda m: str(ids[m.group(1)]), text)
