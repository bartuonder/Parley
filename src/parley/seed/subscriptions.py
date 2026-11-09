import random
from datetime import datetime, timedelta

from parley.db.enums import (
    BillingInterval,
    InvoiceStatus,
    SubscriptionPlan,
    SubscriptionStatus,
)
from parley.db.models import Customer, Invoice, Subscription
from parley.seed.catalog import ANNUAL_DISCOUNT_MONTHS, COUNTRY_CURRENCY, PLAN_PRICES_CENTS
from parley.seed.config import SeedConfig, rng_for

PLANS = (SubscriptionPlan.BASIC, SubscriptionPlan.PRO, SubscriptionPlan.TEAM)
PLAN_WEIGHTS = (50, 35, 15)
STATUSES = (
    SubscriptionStatus.ACTIVE,
    SubscriptionStatus.PAST_DUE,
    SubscriptionStatus.PAUSED,
    SubscriptionStatus.CANCELLED,
)
STATUS_WEIGHTS = (70, 8, 6, 16)
ANNUAL_RATE = 0.25
SCHEDULED_CANCEL_RATE = 0.08
FAILED_INVOICE_RATE = 0.03
DISPUTED_INVOICE_RATE = 0.02
DUPLICATE_CHARGE_RATE = 0.03
LOOKBACK_DAYS = 540
MONTHLY_DAYS = 30
ANNUAL_DAYS = 365


def generate_subscriptions(
    cfg: SeedConfig, customers: list[Customer]
) -> tuple[list[Subscription], list[Invoice]]:
    rng = rng_for(cfg, "subscriptions")
    subscriptions: list[Subscription] = []
    invoices: list[Invoice] = []
    for customer in customers:
        if rng.random() >= cfg.subscription_rate:
            continue
        sub, sub_invoices = _build(rng, cfg.now, customer)
        subscriptions.append(sub)
        invoices.extend(sub_invoices)
    return subscriptions, invoices


def _build(
    rng: random.Random, now: datetime, customer: Customer
) -> tuple[Subscription, list[Invoice]]:
    plan = rng.choices(PLANS, PLAN_WEIGHTS)[0]
    interval = BillingInterval.ANNUAL if rng.random() < ANNUAL_RATE else BillingInterval.MONTHLY
    status = rng.choices(STATUSES, STATUS_WEIGHTS)[0]
    period = timedelta(days=ANNUAL_DAYS if interval == BillingInterval.ANNUAL else MONTHLY_DAYS)

    base = PLAN_PRICES_CENTS[plan]
    price = base * ANNUAL_DISCOUNT_MONTHS if interval == BillingInterval.ANNUAL else base

    lo = max(customer.created_at, now - timedelta(days=LOOKBACK_DAYS))
    hi = now - timedelta(days=1)
    started_at = lo + (hi - lo) * rng.random()

    billing_end = now
    cancelled_at = None
    if status == SubscriptionStatus.CANCELLED:
        cancelled_at = started_at + (hi - started_at) * rng.random()
        billing_end = cancelled_at

    n_periods = int((billing_end - started_at) / period) + 1
    sub = Subscription(
        plan=plan,
        interval=interval,
        status=status,
        price_cents=price,
        currency=COUNTRY_CURRENCY[customer.country],
        started_at=started_at,
        current_period_end=cancelled_at or started_at + n_periods * period,
        cancel_at_period_end=(
            status == SubscriptionStatus.ACTIVE and rng.random() < SCHEDULED_CANCEL_RATE
        ),
        cancelled_at=cancelled_at,
    )
    sub.customer = customer

    if status == SubscriptionStatus.PAUSED:
        n_periods -= 1
    invoices = _build_invoices(rng, sub, customer, started_at, period, n_periods)
    if status == SubscriptionStatus.PAST_DUE and invoices:
        invoices[-1].status = InvoiceStatus.FAILED
    return sub, invoices


def _build_invoices(
    rng: random.Random,
    sub: Subscription,
    customer: Customer,
    started_at: datetime,
    period: timedelta,
    n_periods: int,
) -> list[Invoice]:
    invoices: list[Invoice] = []
    for k in range(n_periods):
        issued_at = started_at + k * period
        draw = rng.random()
        if draw < FAILED_INVOICE_RATE:
            status = InvoiceStatus.FAILED
        elif draw < FAILED_INVOICE_RATE + DISPUTED_INVOICE_RATE:
            status = InvoiceStatus.DISPUTED
        else:
            status = InvoiceStatus.PAID
        invoices.append(_invoice(sub, customer, status, issued_at))
        if status == InvoiceStatus.PAID and rng.random() < DUPLICATE_CHARGE_RATE:
            invoices.append(
                _invoice(sub, customer, InvoiceStatus.PAID, issued_at + timedelta(minutes=2))
            )
    return invoices


def _invoice(
    sub: Subscription, customer: Customer, status: InvoiceStatus, issued_at: datetime
) -> Invoice:
    invoice = Invoice(
        status=status,
        amount_cents=sub.price_cents,
        currency=sub.currency,
        issued_at=issued_at,
    )
    invoice.customer = customer
    invoice.subscription = sub
    return invoice
