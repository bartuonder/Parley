from sqlalchemy import func, select
from sqlalchemy.orm import Session

from parley.db.enums import (
    InvoiceStatus,
    ItemCategory,
    OrderStatus,
    RefundStatus,
    ShipmentStatus,
)
from parley.db.models import Invoice, Order, OrderItem, Refund, Shipment
from parley.seed.config import SeedConfig
from parley.seed.runner import build_world, fingerprint, seed_database, summarize

CFG = SeedConfig()


def test_build_world_is_pure_and_repeatable() -> None:
    a, b = build_world(CFG), build_world(CFG)
    assert [c.email for c in a.customers] == [c.email for c in b.customers]
    assert [o.total_cents for o in a.orders] == [o.total_cents for o in b.orders]
    assert [s.tracking_number for s in a.shipments] == [s.tracking_number for s in b.shipments]


def test_world_sizes_match_config() -> None:
    sizes = summarize(build_world(CFG))
    assert sizes["customers"] == CFG.n_customers
    assert sizes["orders"] > CFG.n_customers
    assert sizes["subscriptions"] > 0
    assert sizes["refunds"] > 0


def test_reseeding_yields_identical_database(seeded: Session) -> None:
    first = fingerprint(seeded)
    seed_database(seeded, CFG)
    assert fingerprint(seeded) == first


def test_different_seed_changes_database(seeded: Session) -> None:
    baseline = fingerprint(seeded)
    seed_database(seeded, SeedConfig(seed=CFG.seed + 1))
    assert fingerprint(seeded) != baseline
    seed_database(seeded, CFG)


def test_order_totals_match_items(seeded: Session) -> None:
    sums = (
        select(OrderItem.order_id, func.sum(OrderItem.quantity * OrderItem.unit_price_cents))
        .group_by(OrderItem.order_id)
        .subquery()
    )
    mismatches = seeded.execute(
        select(Order.id)
        .join(sums, sums.c.order_id == Order.id)
        .where(Order.total_cents != sums.c[1])
    ).all()
    assert mismatches == []


def test_shipment_timestamps_follow_status(seeded: Session) -> None:
    for shipment in seeded.scalars(select(Shipment)):
        if shipment.status == ShipmentStatus.DELIVERED:
            assert shipment.delivered_at is not None
            assert shipment.delivered_at <= CFG.now
        else:
            assert shipment.delivered_at is None
        if shipment.status == ShipmentStatus.LABEL_CREATED:
            assert shipment.shipped_at is None


def test_no_timestamps_in_the_future(seeded: Session) -> None:
    assert not seeded.scalars(select(Order).where(Order.placed_at > CFG.now)).all()
    assert not seeded.scalars(select(Invoice).where(Invoice.issued_at > CFG.now)).all()
    assert not seeded.scalars(select(Refund).where(Refund.created_at > CFG.now)).all()


def test_refunds_are_consistent_with_targets(seeded: Session) -> None:
    for refund in seeded.scalars(select(Refund)):
        target_amount = (
            refund.order.total_cents if refund.order is not None else refund.invoice.amount_cents
        )
        assert refund.amount_cents <= target_amount
        assert (refund.processed_at is not None) == (refund.status == RefundStatus.PROCESSED)


def test_covers_edge_cases_needed_by_eval(seeded: Session) -> None:
    def count(stmt) -> int:
        return seeded.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    assert count(select(Shipment).where(Shipment.status == ShipmentStatus.LOST)) > 0
    assert count(select(Shipment).where(Shipment.status == ShipmentStatus.RETURNED)) > 0
    assert count(select(Shipment).where(Shipment.status == ShipmentStatus.IN_TRANSIT)) > 0
    assert count(select(Order).where(Order.status == OrderStatus.CANCELLED)) > 0
    assert count(select(Order).where(Order.status == OrderStatus.PARTIALLY_REFUNDED)) > 0
    assert count(select(Invoice).where(Invoice.status == InvoiceStatus.FAILED)) > 0
    assert count(select(Invoice).where(Invoice.status == InvoiceStatus.DISPUTED)) > 0
    assert count(select(OrderItem).where(OrderItem.category == ItemCategory.FINAL_SALE)) > 0
    assert count(select(OrderItem).where(OrderItem.category == ItemCategory.DIGITAL)) > 0
