from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from parley.backend.rules import Eligibility, EligibilityCode
from parley.backend.services import RefundTarget
from parley.db.enums import (
    BillingInterval,
    CustomerTier,
    InvoiceStatus,
    ItemCategory,
    OrderStatus,
    RefundStatus,
    ShipmentStatus,
    SubscriptionPlan,
    SubscriptionStatus,
)


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CustomerOut(ORMModel):
    id: int
    email: str
    name: str
    country: str
    tier: CustomerTier
    created_at: datetime


class OrderItemOut(ORMModel):
    sku: str
    name: str
    category: ItemCategory
    quantity: int
    unit_price_cents: int


class ShipmentOut(ORMModel):
    id: int
    order_id: int
    carrier: str
    tracking_number: str
    status: ShipmentStatus
    shipped_at: datetime | None
    estimated_delivery_at: datetime | None
    delivered_at: datetime | None


class RefundOut(ORMModel):
    id: int
    order_id: int | None
    invoice_id: int | None
    amount_cents: int
    currency: str
    reason: str
    status: RefundStatus
    created_at: datetime
    processed_at: datetime | None


class OrderOut(ORMModel):
    id: int
    customer_id: int
    status: OrderStatus
    currency: str
    total_cents: int
    placed_at: datetime
    items: list[OrderItemOut]
    shipments: list[ShipmentOut]
    refunds: list[RefundOut]


class SubscriptionOut(ORMModel):
    id: int
    customer_id: int
    plan: SubscriptionPlan
    interval: BillingInterval
    status: SubscriptionStatus
    price_cents: int
    currency: str
    started_at: datetime
    current_period_end: datetime
    cancel_at_period_end: bool
    cancelled_at: datetime | None


class InvoiceOut(ORMModel):
    id: int
    customer_id: int
    subscription_id: int | None
    status: InvoiceStatus
    amount_cents: int
    currency: str
    issued_at: datetime


class EligibilityOut(BaseModel):
    eligible: bool
    code: EligibilityCode
    max_refund_cents: int

    @classmethod
    def of(cls, e: Eligibility) -> "EligibilityOut":
        return cls(eligible=e.eligible, code=e.code, max_refund_cents=e.max_refund_cents)


class RefundRequest(BaseModel):
    target: RefundTarget
    target_id: int
    amount_cents: int = Field(gt=0)
    reason: str = Field(min_length=1, max_length=500)
    idempotency_key: str = Field(min_length=1, max_length=100)
