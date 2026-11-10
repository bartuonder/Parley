import threading
import time
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from parley.backend.services import (
    Backend,
    BackendError,
    NotEligibleError,
    RefundTarget,
)
from parley.db.enums import OrderStatus, ShipmentStatus
from parley.db.models import Order, Refund
from parley.seed.runner import world_tables
from tests.factories import (
    NOW,
    make_customer,
    make_item,
    make_order,
    make_shipment,
)

CLOCK = NOW.replace(day=20)
TIMEOUT = 10.0


def create_order(session: Session, email: str, tracking: str) -> int:
    order = make_order(session, make_customer(session, email), total_cents=5000)
    make_item(session, order, unit_price_cents=5000)
    make_shipment(session, order, tracking, ShipmentStatus.DELIVERED, delivered_at=NOW)
    order.status = OrderStatus.DELIVERED
    return order.id


@pytest.fixture
def committed_orders(engine: Engine) -> Iterator[tuple[int, int]]:
    with Session(engine) as session:
        ids = (
            create_order(session, "a@example.com", "T-A"),
            create_order(session, "b@example.com", "T-B"),
        )
        session.commit()
    yield ids
    tables = ", ".join(t.name for t in world_tables())
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


def issue(
    engine: Engine,
    order_id: int,
    key: str,
    results: list[str],
    locked: threading.Event,
    release: threading.Event | None = None,
) -> None:
    """Issue a full refund; a request given a release event holds its transaction open."""
    with Session(engine, expire_on_commit=False) as session:
        backend = Backend(session, lambda: CLOCK)
        try:
            refund, created = backend.issue_refund(RefundTarget.ORDER, order_id, 5000, "r", key)
        except BackendError as exc:
            session.rollback()
            results.append(
                type(exc).__name__ + (f":{exc.code}" if isinstance(exc, NotEligibleError) else "")
            )
            return
        locked.set()
        if release is not None:
            release.wait(TIMEOUT)
        session.commit()
        results.append(f"{'created' if created else 'replayed'}:{refund.id}")


def race(
    engine: Engine, first: tuple[int, str], second: tuple[int, str]
) -> tuple[list[str], list[str]]:
    """Run two refunds; the first holds its lock until the second is seen waiting on it."""
    a_results: list[str] = []
    b_results: list[str] = []
    a_locked, b_locked, release = threading.Event(), threading.Event(), threading.Event()
    a = threading.Thread(target=issue, args=(engine, *first, a_results, a_locked, release))
    b = threading.Thread(target=issue, args=(engine, *second, b_results, b_locked))
    a.start()
    assert a_locked.wait(TIMEOUT), "first request never reached its commit point"
    b.start()
    time.sleep(0.5)
    assert b.is_alive(), "second request did not wait for the first"
    release.set()
    a.join(TIMEOUT)
    b.join(TIMEOUT)
    assert not a.is_alive() and not b.is_alive()
    return a_results, b_results


def refund_count(engine: Engine) -> int:
    with Session(engine) as session:
        return session.scalar(select(func.count()).select_from(Refund)) or 0


def test_two_refunds_for_the_same_order_cannot_both_succeed(
    engine: Engine, committed_orders: tuple[int, int]
) -> None:
    order_id, _ = committed_orders
    a, b = race(engine, (order_id, "key-1"), (order_id, "key-2"))
    assert a[0].startswith("created:")
    assert b == ["NotEligibleError:already_refunded"]
    assert refund_count(engine) == 1
    with Session(engine) as session:
        assert session.get_one(Order, order_id).status == OrderStatus.REFUNDED


def test_a_replay_that_races_the_original_returns_the_same_refund(
    engine: Engine, committed_orders: tuple[int, int]
) -> None:
    order_id, _ = committed_orders
    a, b = race(engine, (order_id, "same-key"), (order_id, "same-key"))
    assert a[0].startswith("created:")
    assert b == [a[0].replace("created", "replayed")]
    assert refund_count(engine) == 1


def test_one_key_used_for_two_different_orders_is_a_conflict_not_a_crash(
    engine: Engine, committed_orders: tuple[int, int]
) -> None:
    first, second = committed_orders
    a, b = race(engine, (first, "shared-key"), (second, "shared-key"))
    assert a[0].startswith("created:")
    assert b == ["IdempotencyConflictError"]
    assert refund_count(engine) == 1
