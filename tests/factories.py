from datetime import UTC, datetime

from sqlalchemy.orm import Session

from parley.db.enums import (
    BillingInterval,
    CustomerTier,
    ItemCategory,
    OrderStatus,
    ShipmentStatus,
    SubscriptionPlan,
    SubscriptionStatus,
)
from parley.db.models import Customer, Order, OrderItem, Shipment, Subscription

NOW = datetime(2026, 1, 15, 12, 0, tzinfo=UTC)


def make_customer(session: Session, email: str = "ada@example.com") -> Customer:
    customer = Customer(
        email=email, name="Ada Lovelace", country="GB", tier=CustomerTier.STANDARD, created_at=NOW
    )
    session.add(customer)
    session.flush()
    return customer


def make_order(session: Session, customer: Customer, total_cents: int = 5000) -> Order:
    order = Order(
        customer_id=customer.id,
        status=OrderStatus.PLACED,
        currency="USD",
        total_cents=total_cents,
        placed_at=NOW,
    )
    session.add(order)
    session.flush()
    return order


def make_item(session: Session, order: Order) -> OrderItem:
    item = OrderItem(
        order_id=order.id,
        sku="SKU-1",
        name="Desk lamp",
        category=ItemCategory.PHYSICAL,
        quantity=1,
        unit_price_cents=5000,
    )
    session.add(item)
    session.flush()
    return item


def make_shipment(session: Session, order: Order, tracking: str = "TRK-1") -> Shipment:
    shipment = Shipment(
        order_id=order.id,
        carrier="DHL",
        tracking_number=tracking,
        status=ShipmentStatus.IN_TRANSIT,
        shipped_at=NOW,
    )
    session.add(shipment)
    session.flush()
    return shipment


def make_subscription(session: Session, customer: Customer) -> Subscription:
    sub = Subscription(
        customer_id=customer.id,
        plan=SubscriptionPlan.PRO,
        interval=BillingInterval.MONTHLY,
        status=SubscriptionStatus.ACTIVE,
        price_cents=1900,
        currency="USD",
        started_at=NOW,
        current_period_end=NOW,
    )
    session.add(sub)
    session.flush()
    return sub
