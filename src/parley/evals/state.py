from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from parley.db.enums import InvoiceStatus, OrderStatus, RefundStatus, SubscriptionStatus
from parley.db.models import Invoice, Order, Refund, Subscription
from parley.evals.schema import NewRefund, StateDiff, SubscriptionChange
from parley.evals.world import WorldIndex


@dataclass(frozen=True)
class SubState:
    status: SubscriptionStatus
    cancel_at_period_end: bool


@dataclass(frozen=True)
class Snapshot:
    orders: dict[str, OrderStatus]
    invoices: dict[str, InvoiceStatus]
    subscriptions: dict[str, SubState]
    refunds: dict[int, tuple[str, int, RefundStatus]]


def take_snapshot(session: Session, index: WorldIndex) -> Snapshot:
    session.expire_all()
    order_alias = {v: k for k, v in index.orders.items()}
    invoice_alias = {v: k for k, v in index.invoices.items()}

    orders = {a: session.get(Order, i).status for a, i in index.orders.items()}
    invoices = {a: session.get(Invoice, i).status for a, i in index.invoices.items()}
    subscriptions = {}
    for alias, sub_id in index.subscriptions.items():
        sub = session.get(Subscription, sub_id)
        subscriptions[alias] = SubState(sub.status, sub.cancel_at_period_end)

    refunds: dict[int, tuple[str, int, RefundStatus]] = {}
    for refund in session.scalars(select(Refund)):
        target = order_alias.get(refund.order_id) or invoice_alias.get(refund.invoice_id)
        if target is not None:
            refunds[refund.id] = (target, refund.amount_cents, refund.status)
    return Snapshot(orders, invoices, subscriptions, refunds)


def diff_snapshots(before: Snapshot, after: Snapshot) -> StateDiff:
    """Everything that changed between two snapshots, in the shape scenarios expect."""
    subscriptions: dict[str, SubscriptionChange] = {}
    for alias, new in after.subscriptions.items():
        old = before.subscriptions[alias]
        change = SubscriptionChange(
            status=new.status if new.status != old.status else None,
            cancel_at_period_end=(
                new.cancel_at_period_end
                if new.cancel_at_period_end != old.cancel_at_period_end
                else None
            ),
        )
        if change != SubscriptionChange():
            subscriptions[alias] = change

    new_refunds = [
        NewRefund(target=t, amount_cents=amount, status=status)
        for refund_id, (t, amount, status) in after.refunds.items()
        if refund_id not in before.refunds
    ]
    new_refunds.sort(key=lambda r: (r.target, r.amount_cents, r.status))
    return StateDiff(
        orders={a: s for a, s in after.orders.items() if s != before.orders[a]},
        invoices={a: s for a, s in after.invoices.items() if s != before.invoices[a]},
        subscriptions=subscriptions,
        new_refunds=new_refunds,
    )


def normalize(diff: StateDiff) -> StateDiff:
    """Order-independent form of an expected diff, for comparison."""
    return diff.model_copy(
        update={
            "new_refunds": sorted(
                diff.new_refunds, key=lambda r: (r.target, r.amount_cents, r.status)
            )
        }
    )
