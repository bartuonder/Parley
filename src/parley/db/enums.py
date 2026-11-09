from enum import StrEnum


class CustomerTier(StrEnum):
    STANDARD = "standard"
    PREMIUM = "premium"


class OrderStatus(StrEnum):
    PLACED = "placed"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    PARTIALLY_REFUNDED = "partially_refunded"
    REFUNDED = "refunded"


class ItemCategory(StrEnum):
    PHYSICAL = "physical"
    DIGITAL = "digital"
    FINAL_SALE = "final_sale"


class ShipmentStatus(StrEnum):
    LABEL_CREATED = "label_created"
    IN_TRANSIT = "in_transit"
    DELIVERED = "delivered"
    LOST = "lost"
    RETURNED = "returned"


class SubscriptionPlan(StrEnum):
    BASIC = "basic"
    PRO = "pro"
    TEAM = "team"


class BillingInterval(StrEnum):
    MONTHLY = "monthly"
    ANNUAL = "annual"


class SubscriptionStatus(StrEnum):
    ACTIVE = "active"
    PAST_DUE = "past_due"
    PAUSED = "paused"
    CANCELLED = "cancelled"


class InvoiceStatus(StrEnum):
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"
    DISPUTED = "disputed"


class RefundStatus(StrEnum):
    PENDING_APPROVAL = "pending_approval"
    PROCESSED = "processed"
    REJECTED = "rejected"


class TicketCategory(StrEnum):
    REFUND = "refund"
    SHIPPING = "shipping"
    SUBSCRIPTION = "subscription"
    BILLING = "billing"
    GENERAL = "general"


class TicketOutcome(StrEnum):
    REFUNDED = "refunded"
    DENIED = "denied"
    INFO_PROVIDED = "info_provided"
    ACTION_TAKEN = "action_taken"
    ESCALATED = "escalated"
