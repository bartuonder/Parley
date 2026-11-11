from parley.db.models import Invoice, Order, Shipment, Subscription
from parley.tools.context import ToolContext


class AccessDeniedError(Exception):
    """The record exists but belongs to someone other than the ticket sender."""


def own_order(ctx: ToolContext, order_id: int) -> Order:
    order = ctx.backend.get_order(order_id)
    _check(ctx, order.customer_id)
    return order


def own_invoice(ctx: ToolContext, invoice_id: int) -> Invoice:
    invoice = ctx.backend.get_invoice(invoice_id)
    _check(ctx, invoice.customer_id)
    return invoice


def own_subscription(ctx: ToolContext, subscription_id: int) -> Subscription:
    sub = ctx.backend.get_subscription(subscription_id)
    _check(ctx, sub.customer_id)
    return sub


def own_shipment(ctx: ToolContext, tracking_number: str) -> Shipment:
    shipment = ctx.backend.get_shipment_by_tracking(tracking_number)
    _check(ctx, shipment.order.customer_id)
    return shipment


def _check(ctx: ToolContext, owner_id: int) -> None:
    if owner_id != ctx.customer_id:
        raise AccessDeniedError("this record does not belong to the customer who sent the ticket")
