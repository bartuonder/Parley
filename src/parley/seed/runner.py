import hashlib
import json
from dataclasses import dataclass

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from parley.db.base import Base
from parley.db.models import Customer, Invoice, Order, Refund, Shipment, Subscription
from parley.seed.config import SeedConfig
from parley.seed.customers import generate_customers
from parley.seed.fulfillment import fulfill_orders
from parley.seed.orders import generate_orders
from parley.seed.refunds import generate_refunds
from parley.seed.subscriptions import generate_subscriptions


@dataclass
class World:
    customers: list[Customer]
    orders: list[Order]
    shipments: list[Shipment]
    subscriptions: list[Subscription]
    invoices: list[Invoice]
    refunds: list[Refund]


def build_world(cfg: SeedConfig) -> World:
    customers = generate_customers(cfg)
    orders = generate_orders(cfg, customers)
    shipments = fulfill_orders(cfg, orders)
    subscriptions, invoices = generate_subscriptions(cfg, customers)
    refunds = generate_refunds(cfg, orders, invoices)
    return World(customers, orders, shipments, subscriptions, invoices, refunds)


def reset_database(session: Session) -> None:
    tables = ", ".join(t.name for t in Base.metadata.sorted_tables)
    session.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


def seed_database(session: Session, cfg: SeedConfig) -> World:
    reset_database(session)
    world = build_world(cfg)
    session.add_all(world.customers)
    session.flush()
    return world


def fingerprint(session: Session) -> str:
    """Stable hash of every row in every table, for determinism checks."""
    digest = hashlib.sha256()
    for table in Base.metadata.sorted_tables:
        rows = session.execute(select(table).order_by(table.c.id)).all()
        payload = json.dumps([list(r) for r in rows], default=str, sort_keys=True)
        digest.update(f"{table.name}:{payload}".encode())
    return digest.hexdigest()


def summarize(world: World) -> dict[str, int]:
    return {
        "customers": len(world.customers),
        "orders": len(world.orders),
        "shipments": len(world.shipments),
        "subscriptions": len(world.subscriptions),
        "invoices": len(world.invoices),
        "refunds": len(world.refunds),
    }
