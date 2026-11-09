import random
from datetime import datetime, timedelta

from parley.db.enums import ItemCategory, OrderStatus, ShipmentStatus
from parley.db.models import Order, Shipment
from parley.seed.catalog import CARRIERS
from parley.seed.config import SeedConfig, rng_for

OUTCOMES = ("cancelled", "normal", "late", "lost", "returned", "stuck")
OUTCOME_WEIGHTS = (4, 76, 11, 3, 3, 3)
DOMESTIC_TRANSIT_DAYS = (2, 5)
INTERNATIONAL_TRANSIT_DAYS = (5, 12)
MAX_LATE_DAYS = 21
MIN_AGE_LOST_DAYS = 10
MIN_AGE_STUCK_DAYS = 5


def fulfill_orders(cfg: SeedConfig, orders: list[Order]) -> list[Shipment]:
    rng = rng_for(cfg, "fulfillment")
    shipments: list[Shipment] = []
    for order in orders:
        shipment = _fulfill(rng, cfg.now, order)
        if shipment is not None:
            shipments.append(shipment)
    return shipments


def _fulfill(rng: random.Random, now: datetime, order: Order) -> Shipment | None:
    if all(item.category == ItemCategory.DIGITAL for item in order.items):
        order.status = OrderStatus.DELIVERED
        return None

    outcome = rng.choices(OUTCOMES, OUTCOME_WEIGHTS)[0]
    age = now - order.placed_at
    if outcome == "cancelled":
        order.status = OrderStatus.CANCELLED
        return None
    if outcome == "stuck" and age.days < MIN_AGE_STUCK_DAYS:
        outcome = "normal"
    if outcome == "lost" and age.days < MIN_AGE_LOST_DAYS:
        outcome = "normal"

    carrier, prefix = rng.choice(CARRIERS)
    shipment = Shipment(
        carrier=carrier,
        tracking_number=f"{prefix}{rng.randrange(10**10):010d}",
        status=ShipmentStatus.LABEL_CREATED,
    )
    shipment.order = order

    if outcome == "stuck" or age < timedelta(days=1):
        order.status = OrderStatus.PLACED
        return shipment

    shipped_at = order.placed_at + timedelta(hours=rng.randint(6, 60))
    if shipped_at > now:
        order.status = OrderStatus.PLACED
        return shipment

    shipment.shipped_at = shipped_at
    low, high = _transit_range(order)
    shipment.estimated_delivery_at = shipped_at + timedelta(days=rng.randint(low, high))
    order.status = OrderStatus.SHIPPED
    shipment.status = ShipmentStatus.IN_TRANSIT

    eta = shipment.estimated_delivery_at
    if outcome == "lost":
        shipment.status = ShipmentStatus.LOST
    elif outcome == "returned":
        shipment.status = ShipmentStatus.RETURNED
    elif not (outcome == "late" and timedelta(0) < now - eta <= timedelta(days=MAX_LATE_DAYS)):
        delivered_at = eta + timedelta(hours=rng.randint(-24, 24))
        if delivered_at <= now:
            shipment.status = ShipmentStatus.DELIVERED
            shipment.delivered_at = delivered_at
            order.status = OrderStatus.DELIVERED
    return shipment


def _transit_range(order: Order) -> tuple[int, int]:
    domestic = order.customer.country in ("US", "CA")
    return DOMESTIC_TRANSIT_DAYS if domestic else INTERNATIONAL_TRANSIT_DAYS
