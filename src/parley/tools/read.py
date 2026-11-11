from typing import Any

from pydantic import BaseModel, Field

from parley.backend.rules import APPROVAL_THRESHOLD_CENTS
from parley.backend.schemas import (
    CustomerOut,
    EligibilityOut,
    InvoiceOut,
    OrderOut,
    ShipmentOut,
    SubscriptionOut,
)
from parley.backend.services import RefundTarget
from parley.tools.access import own_invoice, own_order, own_shipment, own_subscription
from parley.tools.context import ToolContext
from parley.tools.permissions import Permission
from parley.tools.registry import ToolParams, ToolSpec


class NoParams(ToolParams):
    pass


class OrderParams(ToolParams):
    order_id: int = Field(description="Order id")


class InvoiceParams(ToolParams):
    invoice_id: int = Field(description="Invoice id")


class SubscriptionParams(ToolParams):
    subscription_id: int = Field(description="Subscription id")


class ShipmentParams(ToolParams):
    tracking_number: str = Field(min_length=1, description="Carrier tracking number")


class EligibilityParams(ToolParams):
    target: RefundTarget = Field(description="Whether target_id is an order or an invoice")
    target_id: int


class Overview(BaseModel):
    customer: CustomerOut
    orders: list[OrderOut]
    subscriptions: list[SubscriptionOut]
    invoices: list[InvoiceOut]


class Eligibility(EligibilityOut):
    approval_required_above_cents: int = APPROVAL_THRESHOLD_CENTS


def get_customer_overview(ctx: ToolContext, params: NoParams) -> Overview:
    backend = ctx.backend
    return Overview(
        customer=CustomerOut.model_validate(backend.get_customer(ctx.customer_id)),
        orders=[OrderOut.model_validate(o) for o in backend.list_orders(ctx.customer_id)],
        subscriptions=[
            SubscriptionOut.model_validate(s) for s in backend.list_subscriptions(ctx.customer_id)
        ],
        invoices=[InvoiceOut.model_validate(i) for i in backend.list_invoices(ctx.customer_id)],
    )


def get_order(ctx: ToolContext, params: OrderParams) -> OrderOut:
    return OrderOut.model_validate(own_order(ctx, params.order_id))


def get_shipment(ctx: ToolContext, params: ShipmentParams) -> ShipmentOut:
    return ShipmentOut.model_validate(own_shipment(ctx, params.tracking_number))


def get_subscription(ctx: ToolContext, params: SubscriptionParams) -> SubscriptionOut:
    return SubscriptionOut.model_validate(own_subscription(ctx, params.subscription_id))


def get_invoice(ctx: ToolContext, params: InvoiceParams) -> InvoiceOut:
    return InvoiceOut.model_validate(own_invoice(ctx, params.invoice_id))


def check_refund_eligibility(ctx: ToolContext, params: EligibilityParams) -> Eligibility:
    if params.target == RefundTarget.ORDER:
        own_order(ctx, params.target_id)
        result = ctx.backend.check_order_refund(params.target_id)
    else:
        own_invoice(ctx, params.target_id)
        result = ctx.backend.check_invoice_refund(params.target_id)
    return Eligibility.model_validate(EligibilityOut.of(result).model_dump())


READ_TOOLS: list[ToolSpec[Any]] = [
    ToolSpec(
        "get_customer_overview",
        "Profile, orders with items, shipments and refunds, subscriptions and invoices of the "
        "customer who sent the ticket.",
        Permission.READ,
        NoParams,
        get_customer_overview,
    ),
    ToolSpec(
        "get_order",
        "One order of the sender with items, shipments and refunds.",
        Permission.READ,
        OrderParams,
        get_order,
    ),
    ToolSpec(
        "get_shipment",
        "Shipment status and dates for a tracking number of the sender's orders.",
        Permission.READ,
        ShipmentParams,
        get_shipment,
    ),
    ToolSpec(
        "get_subscription",
        "One subscription of the sender.",
        Permission.READ,
        SubscriptionParams,
        get_subscription,
    ),
    ToolSpec(
        "get_invoice",
        "One invoice of the sender.",
        Permission.READ,
        InvoiceParams,
        get_invoice,
    ),
    ToolSpec(
        "check_refund_eligibility",
        "Whether an order or invoice can be refunded now, the reason code and the maximum "
        "refundable amount in cents. Refunds above the approval threshold wait for a human.",
        Permission.READ,
        EligibilityParams,
        check_refund_eligibility,
    ),
]
