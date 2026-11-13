from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

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
    TicketCategory,
)


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class ItemSpec(Strict):
    sku: str
    name: str
    category: ItemCategory = ItemCategory.PHYSICAL
    quantity: int = Field(default=1, gt=0)
    unit_price_cents: int = Field(ge=0)


class ShipmentSpec(Strict):
    status: ShipmentStatus
    carrier: str = "DHL"
    shipped_days_ago: float | None = None
    eta_days_from_now: float | None = None
    delivered_days_ago: float | None = None


class OrderSpec(Strict):
    alias: str
    status: OrderStatus
    placed_days_ago: float
    items: list[ItemSpec] = Field(min_length=1)
    shipment: ShipmentSpec | None = None


class SubscriptionSpec(Strict):
    alias: str
    plan: SubscriptionPlan = SubscriptionPlan.PRO
    interval: BillingInterval = BillingInterval.MONTHLY
    status: SubscriptionStatus = SubscriptionStatus.ACTIVE
    price_cents: int = Field(ge=0)
    started_days_ago: float
    period_end_days_from_now: float
    cancel_at_period_end: bool = False


class InvoiceSpec(Strict):
    alias: str
    subscription: str | None = None
    status: InvoiceStatus = InvoiceStatus.PAID
    amount_cents: int = Field(ge=0)
    issued_days_ago: float


class RefundSpec(Strict):
    alias: str
    order: str | None = None
    invoice: str | None = None
    amount_cents: int = Field(gt=0)
    status: RefundStatus = RefundStatus.PROCESSED
    reason: str = "seeded"
    created_days_ago: float = 5

    @model_validator(mode="after")
    def exactly_one_target(self) -> Self:
        if (self.order is None) == (self.invoice is None):
            raise ValueError("refund needs exactly one of order or invoice")
        return self


class CustomerSpec(Strict):
    alias: str
    email: str
    name: str
    country: str = "US"
    tier: CustomerTier = CustomerTier.STANDARD
    orders: list[OrderSpec] = Field(default_factory=list)
    subscriptions: list[SubscriptionSpec] = Field(default_factory=list)
    invoices: list[InvoiceSpec] = Field(default_factory=list)
    refunds: list[RefundSpec] = Field(default_factory=list)


class TicketSpec(Strict):
    sender_email: str
    subject: str
    body: str


class ActionSpec(Strict):
    tool: Literal["issue_refund", "cancel_subscription"]
    alias: str
    target: Literal["order", "invoice"] | None = None
    amount_cents: int | None = None

    @model_validator(mode="after")
    def tool_arguments(self) -> Self:
        if self.tool == "issue_refund" and (self.target is None or self.amount_cents is None):
            raise ValueError("issue_refund needs target and amount_cents")
        if self.tool == "cancel_subscription" and (self.target or self.amount_cents):
            raise ValueError("cancel_subscription takes only an alias")
        return self


class SubscriptionChange(Strict):
    status: SubscriptionStatus | None = None
    cancel_at_period_end: bool | None = None


class NewRefund(Strict):
    target: str
    amount_cents: int
    status: RefundStatus


class StateDiff(Strict):
    orders: dict[str, OrderStatus] = Field(default_factory=dict)
    invoices: dict[str, InvoiceStatus] = Field(default_factory=dict)
    subscriptions: dict[str, SubscriptionChange] = Field(default_factory=dict)
    new_refunds: list[NewRefund] = Field(default_factory=list)


class Expected(Strict):
    diff: StateDiff = Field(default_factory=StateDiff)
    requires_human: bool = False
    handover_open: bool = False
    policy_refs: list[str] = Field(default_factory=list)
    reply_facts: list[str] = Field(default_factory=list)


class MemorySpec(Strict):
    customer: str
    kind: str
    content: str
    ticket_id: str = "T-PRIOR"
    days_ago: float = 5


class Scenario(Strict):
    id: str = Field(pattern=r"^[A-Z]{3}-\d{3}$")
    category: TicketCategory
    difficulty: Literal["easy", "medium", "hard"]
    tags: list[str] = Field(default_factory=list)
    description: str
    world: list[CustomerSpec] = Field(min_length=1)
    ticket: TicketSpec
    expected: Expected
    reference_actions: list[ActionSpec] = Field(default_factory=list)
    forbidden_actions: list[ActionSpec] = Field(default_factory=list)
    memory: list[MemorySpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def aliases_are_unique(self) -> Self:
        aliases: list[str] = []
        for c in self.world:
            aliases.append(c.alias)
            for group in (c.orders, c.subscriptions, c.invoices, c.refunds):
                aliases.extend(item.alias for item in group)
        duplicates = sorted({a for a in aliases if aliases.count(a) > 1})
        if duplicates:
            raise ValueError(f"duplicate aliases: {duplicates}")
        return self

    @model_validator(mode="after")
    def memory_belongs_to_a_customer(self) -> Self:
        owners = {c.alias for c in self.world}
        unknown = sorted({m.customer for m in self.memory} - owners)
        if unknown:
            raise ValueError(f"memory for unknown customers: {unknown}")
        return self
