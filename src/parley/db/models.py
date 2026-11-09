from datetime import datetime
from enum import StrEnum

from sqlalchemy import CheckConstraint, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from parley.db.base import Base
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
    TicketOutcome,
)


def enum_col(enum_cls: type[StrEnum]) -> Enum:
    return Enum(
        enum_cls,
        native_enum=False,
        create_constraint=True,
        length=32,
        values_callable=lambda e: [m.value for m in e],
    )


def tstz() -> DateTime:
    return DateTime(timezone=True)


class Customer(Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    name: Mapped[str] = mapped_column(String(120))
    country: Mapped[str] = mapped_column(String(2))
    tier: Mapped[CustomerTier] = mapped_column(enum_col(CustomerTier))
    created_at: Mapped[datetime] = mapped_column(tstz())

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")
    subscriptions: Mapped[list["Subscription"]] = relationship(back_populates="customer")


class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    status: Mapped[OrderStatus] = mapped_column(enum_col(OrderStatus))
    currency: Mapped[str] = mapped_column(String(3))
    total_cents: Mapped[int] = mapped_column(Integer)
    placed_at: Mapped[datetime] = mapped_column(tstz())

    customer: Mapped[Customer] = relationship(back_populates="orders")
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order")
    shipments: Mapped[list["Shipment"]] = relationship(back_populates="order")
    refunds: Mapped[list["Refund"]] = relationship(back_populates="order")

    __table_args__ = (CheckConstraint("total_cents >= 0", name="total_non_negative"),)


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    sku: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[ItemCategory] = mapped_column(enum_col(ItemCategory))
    quantity: Mapped[int] = mapped_column(Integer)
    unit_price_cents: Mapped[int] = mapped_column(Integer)

    order: Mapped[Order] = relationship(back_populates="items")

    __table_args__ = (
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("unit_price_cents >= 0", name="price_non_negative"),
    )


class Shipment(Base):
    __tablename__ = "shipments"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), index=True)
    carrier: Mapped[str] = mapped_column(String(40))
    tracking_number: Mapped[str] = mapped_column(String(60), unique=True)
    status: Mapped[ShipmentStatus] = mapped_column(enum_col(ShipmentStatus))
    shipped_at: Mapped[datetime | None] = mapped_column(tstz())
    estimated_delivery_at: Mapped[datetime | None] = mapped_column(tstz())
    delivered_at: Mapped[datetime | None] = mapped_column(tstz())

    order: Mapped[Order] = relationship(back_populates="shipments")


class Subscription(Base):
    __tablename__ = "subscriptions"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    plan: Mapped[SubscriptionPlan] = mapped_column(enum_col(SubscriptionPlan))
    interval: Mapped[BillingInterval] = mapped_column(enum_col(BillingInterval))
    status: Mapped[SubscriptionStatus] = mapped_column(enum_col(SubscriptionStatus))
    price_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    started_at: Mapped[datetime] = mapped_column(tstz())
    current_period_end: Mapped[datetime] = mapped_column(tstz())
    cancel_at_period_end: Mapped[bool] = mapped_column(default=False)
    cancelled_at: Mapped[datetime | None] = mapped_column(tstz())

    customer: Mapped[Customer] = relationship(back_populates="subscriptions")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="subscription")

    __table_args__ = (CheckConstraint("price_cents >= 0", name="price_non_negative"),)


class Invoice(Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    subscription_id: Mapped[int | None] = mapped_column(ForeignKey("subscriptions.id"), index=True)
    status: Mapped[InvoiceStatus] = mapped_column(enum_col(InvoiceStatus))
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    issued_at: Mapped[datetime] = mapped_column(tstz())

    customer: Mapped[Customer] = relationship()
    subscription: Mapped[Subscription | None] = relationship(back_populates="invoices")
    refunds: Mapped[list["Refund"]] = relationship(back_populates="invoice")

    __table_args__ = (CheckConstraint("amount_cents >= 0", name="amount_non_negative"),)


class Refund(Base):
    __tablename__ = "refunds"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), index=True)
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), index=True)
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    reason: Mapped[str] = mapped_column(Text)
    status: Mapped[RefundStatus] = mapped_column(enum_col(RefundStatus))
    idempotency_key: Mapped[str] = mapped_column(String(100), unique=True)
    created_at: Mapped[datetime] = mapped_column(tstz())
    processed_at: Mapped[datetime | None] = mapped_column(tstz())

    order: Mapped[Order | None] = relationship(back_populates="refunds")
    invoice: Mapped[Invoice | None] = relationship(back_populates="refunds")

    __table_args__ = (
        CheckConstraint("amount_cents > 0", name="amount_positive"),
        CheckConstraint("(order_id IS NOT NULL) <> (invoice_id IS NOT NULL)", name="single_target"),
    )


class Ticket(Base):
    __tablename__ = "tickets"

    id: Mapped[int] = mapped_column(primary_key=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), index=True)
    order_id: Mapped[int | None] = mapped_column(ForeignKey("orders.id"), index=True)
    invoice_id: Mapped[int | None] = mapped_column(ForeignKey("invoices.id"), index=True)
    subscription_id: Mapped[int | None] = mapped_column(ForeignKey("subscriptions.id"), index=True)
    category: Mapped[TicketCategory] = mapped_column(enum_col(TicketCategory))
    outcome: Mapped[TicketOutcome] = mapped_column(enum_col(TicketOutcome))
    subject: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    resolution: Mapped[str] = mapped_column(Text)
    policy_refs: Mapped[list[str]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(tstz())
    resolved_at: Mapped[datetime] = mapped_column(tstz())

    customer: Mapped[Customer] = relationship()
    order: Mapped[Order | None] = relationship()
    invoice: Mapped[Invoice | None] = relationship()
    subscription: Mapped[Subscription | None] = relationship()
