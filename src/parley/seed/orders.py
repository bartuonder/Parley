import random
from datetime import timedelta

from parley.db.enums import OrderStatus
from parley.db.models import Customer, Order, OrderItem
from parley.seed.catalog import COUNTRY_CURRENCY, PRODUCTS
from parley.seed.config import SeedConfig, rng_for

ORDERS_PER_CUSTOMER_WEIGHTS = (5, 15, 25, 25, 20, 10)
ITEMS_PER_ORDER_WEIGHTS = (50, 30, 15, 5)
QUANTITY_WEIGHTS = (80, 15, 5)


def generate_orders(cfg: SeedConfig, customers: list[Customer]) -> list[Order]:
    rng = rng_for(cfg, "orders")
    counts = list(range(cfg.max_orders_per_customer + 1))
    weights = ORDERS_PER_CUSTOMER_WEIGHTS[: len(counts)]
    history_start = cfg.now - timedelta(days=cfg.history_days)
    orders: list[Order] = []
    for customer in customers:
        window_start = max(customer.created_at, history_start)
        window_seconds = int((cfg.now - timedelta(days=1) - window_start).total_seconds())
        if window_seconds <= 0:
            continue
        for _ in range(rng.choices(counts, weights)[0]):
            placed_at = window_start + timedelta(seconds=rng.randrange(window_seconds))
            order = Order(
                status=OrderStatus.PLACED,
                currency=COUNTRY_CURRENCY[customer.country],
                total_cents=0,
                placed_at=placed_at,
            )
            order.customer = customer
            order.items = _generate_items(rng)
            order.total_cents = sum(i.quantity * i.unit_price_cents for i in order.items)
            orders.append(order)
    return orders


def _generate_items(rng: random.Random) -> list[OrderItem]:
    n_items = rng.choices(range(1, len(ITEMS_PER_ORDER_WEIGHTS) + 1), ITEMS_PER_ORDER_WEIGHTS)[0]
    items: list[OrderItem] = []
    for product in rng.sample(PRODUCTS, n_items):
        items.append(
            OrderItem(
                sku=product.sku,
                name=product.name,
                category=product.category,
                quantity=rng.choices((1, 2, 3), QUANTITY_WEIGHTS)[0],
                unit_price_cents=product.price_cents,
            )
        )
    return items
