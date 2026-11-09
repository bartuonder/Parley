from dataclasses import dataclass
from enum import StrEnum

from parley.db.enums import TicketCategory, TicketOutcome


class Kind(StrEnum):
    REFUND_GRANTED = "refund_granted"
    REFUND_DENIED_WINDOW = "refund_denied_window"
    REFUND_DENIED_FINAL_SALE = "refund_denied_final_sale"
    LOST_PACKAGE_REFUND = "lost_package_refund"
    LATE_PACKAGE = "late_package"
    STUCK_LABEL = "stuck_label"
    WHERE_IS_MY_ORDER = "where_is_my_order"
    CANCEL_SUBSCRIPTION = "cancel_subscription"
    FAILED_PAYMENT = "failed_payment"
    DUPLICATE_CHARGE_REFUND = "duplicate_charge_refund"
    ANNUAL_RENEWAL_REFUND = "annual_renewal_refund"
    DISPUTED_INVOICE = "disputed_invoice"
    FAQ_INVOICE_COPY = "faq_invoice_copy"
    FAQ_PREMIUM = "faq_premium"
    FAQ_DELIVERY_TIMES = "faq_delivery_times"
    FAQ_PRICING = "faq_pricing"


@dataclass(frozen=True)
class Template:
    category: TicketCategory
    outcome: TicketOutcome
    policy_ids: tuple[str, ...]
    subjects: tuple[str, ...]
    bodies: tuple[str, ...]
    replies: tuple[str, ...]


R, S, U, B, G = (
    TicketCategory.REFUND,
    TicketCategory.SHIPPING,
    TicketCategory.SUBSCRIPTION,
    TicketCategory.BILLING,
    TicketCategory.GENERAL,
)
OC = TicketOutcome

TEMPLATES: dict[Kind, Template] = {
    Kind.REFUND_GRANTED: Template(
        R,
        OC.REFUNDED,
        ("POL-REF-001", "POL-REF-006", "POL-REF-009"),
        ("Refund for order #{order_id}", "Returning my {item}", "I want my money back"),
        (
            "Hi, I ordered a {item} (order #{order_id}) and it is not what I expected. Reason: "
            "{reason}. Can I get a refund of {amount}?",
            "Order #{order_id}: the {item} has a problem ({reason}). I would like a refund.",
            "Hello, I need to return the {item} from order #{order_id}. {reason}.",
        ),
        (
            "Hi {name}, the order is inside the return window, so we refunded {amount} to your "
            "original payment method. It should appear within 5 to 10 business days.",
            "Thanks for getting in touch, {name}. Your refund of {amount} for order #{order_id} "
            "has been processed under our returns policy.",
        ),
    ),
    Kind.REFUND_DENIED_WINDOW: Template(
        R,
        OC.DENIED,
        ("POL-REF-001", "POL-GEN-003"),
        ("Late return, order #{order_id}", "Can I still return this?", "Refund request"),
        (
            "I know it has been a while, but can I still return the {item} from order "
            "#{order_id}? I never used it.",
            "Order #{order_id} was delivered some weeks ago. I would like to send the {item} back "
            "for a refund.",
        ),
        (
            "Hi {name}, I am sorry, but order #{order_id} was delivered more than {days} days ago "
            "and the return window has closed, so we cannot refund it. I can ask a colleague to "
            "review the case if you would like.",
            "Thank you for your patience, {name}. The returns window for this order ended, "
            "so a refund is not possible under our policy.",
        ),
    ),
    Kind.REFUND_DENIED_FINAL_SALE: Template(
        R,
        OC.DENIED,
        ("POL-REF-003", "POL-PRM-002"),
        ("Returning a clearance item", "Refund for {item}", "Order #{order_id} return"),
        (
            "I bought the {item} in order #{order_id}, but it does not suit me. Can I return it?",
            "Please refund the {item} from order #{order_id}. I changed my mind.",
        ),
        (
            "Hi {name}, the {item} was sold as a final-sale item, so it cannot be returned or "
            "refunded. I am sorry for the inconvenience.",
            "Thanks for asking, {name}. Final-sale items, including clearance and personalized "
            "goods, are not refundable.",
        ),
    ),
    Kind.LOST_PACKAGE_REFUND: Template(
        S,
        OC.REFUNDED,
        ("POL-REF-005", "POL-SHP-003"),
        ("Package never arrived, order #{order_id}", "Lost parcel", "Where is my {item}?"),
        (
            "My package {tracking} with {carrier} has not arrived and tracking shows no update. "
            "Order #{order_id}.",
            "The {item} from order #{order_id} never showed up. Tracking number {tracking}.",
        ),
        (
            "Hi {name}, the carrier lost this parcel, so we refunded {amount} in full. Sorry "
            "about the trouble.",
            "Thanks for waiting, {name}. Because the shipment qualifies as lost, we refunded "
            "order #{order_id} in full ({amount}).",
        ),
    ),
    Kind.LATE_PACKAGE: Template(
        S,
        OC.INFO_PROVIDED,
        ("POL-SHP-003", "POL-SHP-001"),
        ("My order is late", "Delivery delayed, order #{order_id}", "Still waiting for my parcel"),
        (
            "Order #{order_id} should have arrived by now. Tracking {tracking} with {carrier} "
            "still says in transit.",
            "My {item} is late. Can you tell me where it is?",
        ),
        (
            "Hi {name}, {carrier} still shows the parcel in transit. It is past the estimate, but "
            "not yet counted as lost. Please give it a few more days; we will refund the order "
            "if it does not arrive.",
            "I am sorry for the delay, {name}. The parcel {tracking} is moving with {carrier}. "
            "A refund is not available until it is more than 10 days late.",
        ),
    ),
    Kind.STUCK_LABEL: Template(
        S,
        OC.ESCALATED,
        ("POL-SHP-003", "POL-ESC-001"),
        ("Order never shipped", "No tracking movement, order #{order_id}"),
        (
            "Order #{order_id} was placed days ago and tracking only says label created.",
            "The {item} still has not left the warehouse according to tracking {tracking}.",
        ),
        (
            "Hi {name}, the carrier has not collected your parcel. I have passed this to the "
            "fulfillment team and they will follow up with you.",
        ),
    ),
    Kind.WHERE_IS_MY_ORDER: Template(
        S,
        OC.INFO_PROVIDED,
        ("POL-SHP-002", "POL-SHP-001"),
        ("Where is order #{order_id}?", "Tracking question", "Delivery date"),
        (
            "Hello, can you tell me the status of order #{order_id}?",
            "When will my {item} arrive? Tracking number {tracking}.",
        ),
        (
            "Hi {name}, your parcel {tracking} is with {carrier} and is on its way. The estimated "
            "delivery date is {eta}.",
        ),
    ),
    Kind.CANCEL_SUBSCRIPTION: Template(
        U,
        OC.ACTION_TAKEN,
        ("POL-SUB-002",),
        ("Cancel my subscription", "Please cancel my {plan} plan", "Stop billing me"),
        (
            "I no longer need the {plan} plan. Please cancel it.",
            "Cancel my subscription, I will not use it anymore.",
        ),
        (
            "Hi {name}, your {plan} subscription is set to cancel at the end of the current "
            "billing period. You keep access until then, and there will be no further charges.",
        ),
    ),
    Kind.FAILED_PAYMENT: Template(
        B,
        OC.INFO_PROVIDED,
        ("POL-BIL-002", "POL-SUB-005"),
        ("Payment failed", "My card was declined for my subscription", "Past due notice"),
        (
            "I got an email that my payment failed, but my card is fine. What happened?",
            "Why does my account say past due? Invoice #{invoice_id}.",
        ),
        (
            "Hi {name}, invoice #{invoice_id} was not collected, so you have not been charged. "
            "Please update your payment method; we retry the payment for 7 days.",
        ),
    ),
    Kind.DUPLICATE_CHARGE_REFUND: Template(
        B,
        OC.REFUNDED,
        ("POL-BIL-001",),
        ("I was charged twice", "Duplicate charge", "Double billing on my card"),
        (
            "My bank statement shows two identical charges of {amount} on the same day.",
            "I was billed twice for my {plan} subscription. Invoice #{invoice_id} looks like a "
            "duplicate.",
        ),
        (
            "Hi {name}, we confirmed a duplicate charge on invoice #{invoice_id} and refunded "
            "{amount} in full. Sorry about that.",
        ),
    ),
    Kind.ANNUAL_RENEWAL_REFUND: Template(
        U,
        OC.REFUNDED,
        ("POL-SUB-003", "POL-SUB-006"),
        ("Unexpected annual renewal", "I did not mean to renew", "Annual charge refund"),
        (
            "My annual {plan} plan renewed and I did not want that. Can I get the {amount} back?",
            "I was charged {amount} for a yearly renewal a few days ago. Please refund it.",
        ),
        (
            "Hi {name}, the renewal was charged within the cooling-off period, so we refunded "
            "{amount} in full.",
        ),
    ),
    Kind.DISPUTED_INVOICE: Template(
        B,
        OC.ESCALATED,
        ("POL-BIL-003", "POL-ESC-001"),
        ("Refund for disputed charge", "I opened a dispute with my bank", "Chargeback question"),
        (
            "I disputed invoice #{invoice_id} with my bank but now I want a refund from you too.",
            "My bank has a dispute open for {amount}. Can you refund me directly?",
        ),
        (
            "Hi {name}, because invoice #{invoice_id} is under dispute, we cannot issue a refund "
            "ourselves. I have passed your request to the disputes team.",
        ),
    ),
    Kind.FAQ_INVOICE_COPY: Template(
        G,
        OC.INFO_PROVIDED,
        ("POL-BIL-005",),
        ("Where can I find my invoices?", "Need a copy of my invoice"),
        ("Can I download my past invoices? I need them for my records.",),
        (
            "Hi {name}, you can find every invoice in the billing section of your account, "
            "with its status and amount.",
        ),
    ),
    Kind.FAQ_PREMIUM: Template(
        G,
        OC.INFO_PROVIDED,
        ("POL-GEN-004", "POL-REF-002"),
        ("What do premium members get?", "Premium benefits"),
        ("What does the premium membership include?",),
        (
            "Hi {name}, premium members get extended returns of 45 days from delivery and "
            "priority support.",
        ),
    ),
    Kind.FAQ_DELIVERY_TIMES: Template(
        G,
        OC.INFO_PROVIDED,
        ("POL-SHP-001",),
        ("How long does delivery take?", "Shipping times"),
        ("How many days does shipping usually take to my country?",),
        (
            "Hi {name}, orders are dispatched within 1 to 3 days. Domestic parcels take 2 to 5 "
            "days after dispatch and international parcels 5 to 12 days.",
        ),
    ),
    Kind.FAQ_PRICING: Template(
        G,
        OC.INFO_PROVIDED,
        ("POL-SUB-001",),
        ("Subscription prices", "How much is the Pro plan?"),
        ("What are the prices of your subscription plans, and is there an annual discount?",),
        (
            "Hi {name}, the plans are billed monthly, and the annual option costs ten times the "
            "monthly price, which is two months free.",
        ),
    ),
}
