from collections.abc import Callable, Sequence
from datetime import datetime, timedelta
from enum import StrEnum

from sqlalchemy import select
from sqlalchemy.orm import Session

from parley.backend.rules import (
    ACTIVE_REFUND_STATUSES,
    Eligibility,
    invoice_refund_eligibility,
    order_refund_eligibility,
    requires_approval,
)
from parley.db.enums import InvoiceStatus, OrderStatus, RefundStatus, SubscriptionStatus
from parley.db.models import Customer, Invoice, Order, Refund, Shipment, Subscription

DUPLICATE_CHARGE_WINDOW = timedelta(days=1)


class BackendError(Exception):
    pass


class NotFoundError(BackendError):
    pass


class NotEligibleError(BackendError):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class InvalidRequestError(BackendError):
    pass


class IdempotencyConflictError(BackendError):
    pass


class RefundTarget(StrEnum):
    ORDER = "order"
    INVOICE = "invoice"


class Backend:
    def __init__(self, session: Session, now: Callable[[], datetime]) -> None:
        self.session = session
        self.now = now

    def get_customer(self, customer_id: int) -> Customer:
        return self._get(Customer, customer_id)

    def find_customer_by_email(self, email: str) -> Customer:
        customer = self.session.scalar(select(Customer).where(Customer.email == email.lower()))
        if customer is None:
            raise NotFoundError(f"customer with email {email} not found")
        return customer

    def list_orders(self, customer_id: int) -> Sequence[Order]:
        self.get_customer(customer_id)
        stmt = select(Order).where(Order.customer_id == customer_id).order_by(Order.placed_at)
        return self.session.scalars(stmt).all()

    def get_order(self, order_id: int) -> Order:
        return self._get(Order, order_id)

    def get_shipment_by_tracking(self, tracking_number: str) -> Shipment:
        stmt = select(Shipment).where(Shipment.tracking_number == tracking_number)
        shipment = self.session.scalar(stmt)
        if shipment is None:
            raise NotFoundError(f"shipment {tracking_number} not found")
        return shipment

    def list_subscriptions(self, customer_id: int) -> Sequence[Subscription]:
        self.get_customer(customer_id)
        stmt = select(Subscription).where(Subscription.customer_id == customer_id)
        return self.session.scalars(stmt.order_by(Subscription.id)).all()

    def get_subscription(self, subscription_id: int) -> Subscription:
        return self._get(Subscription, subscription_id)

    def list_invoices(self, customer_id: int) -> Sequence[Invoice]:
        self.get_customer(customer_id)
        stmt = select(Invoice).where(Invoice.customer_id == customer_id)
        return self.session.scalars(stmt.order_by(Invoice.issued_at, Invoice.id)).all()

    def get_invoice(self, invoice_id: int) -> Invoice:
        return self._get(Invoice, invoice_id)

    def check_order_refund(self, order_id: int) -> Eligibility:
        return order_refund_eligibility(self.get_order(order_id), self.now())

    def check_invoice_refund(self, invoice_id: int) -> Eligibility:
        invoice = self.get_invoice(invoice_id)
        return invoice_refund_eligibility(invoice, self._has_earlier_duplicate(invoice), self.now())

    def issue_refund(
        self,
        target: RefundTarget,
        target_id: int,
        amount_cents: int,
        reason: str,
        idempotency_key: str,
    ) -> tuple[Refund, bool]:
        """Return the refund and whether this call created it (False on an idempotent replay)."""
        existing = self.session.scalar(
            select(Refund).where(Refund.idempotency_key == idempotency_key)
        )
        if existing is not None:
            if not _same_request(existing, target, target_id, amount_cents):
                raise IdempotencyConflictError(f"key {idempotency_key} used for another request")
            return existing, False

        if amount_cents <= 0:
            raise InvalidRequestError("amount must be positive")
        order, invoice = self._resolve_target(target, target_id)
        eligibility = (
            order_refund_eligibility(order, self.now())
            if order is not None
            else invoice_refund_eligibility(
                invoice, self._has_earlier_duplicate(invoice), self.now()
            )
        )
        if not eligibility.eligible:
            raise NotEligibleError(eligibility.code)
        if amount_cents > eligibility.max_refund_cents:
            raise InvalidRequestError(
                f"amount exceeds refundable maximum of {eligibility.max_refund_cents}"
            )

        needs_approval = requires_approval(amount_cents)
        refund = Refund(
            order=order,
            invoice=invoice,
            amount_cents=amount_cents,
            currency=(order or invoice).currency,
            reason=reason,
            status=RefundStatus.PENDING_APPROVAL if needs_approval else RefundStatus.PROCESSED,
            idempotency_key=idempotency_key,
            created_at=self.now(),
            processed_at=None if needs_approval else self.now(),
        )
        self.session.add(refund)
        self.session.flush()
        if not needs_approval:
            self._apply_processed(refund)
        return refund, True

    def resolve_refund(self, refund_id: int, approve: bool) -> Refund:
        refund = self._get(Refund, refund_id)
        if refund.status != RefundStatus.PENDING_APPROVAL:
            raise InvalidRequestError(f"refund is {refund.status}, not pending approval")
        if approve:
            refund.status = RefundStatus.PROCESSED
            refund.processed_at = self.now()
            self._apply_processed(refund)
        else:
            refund.status = RefundStatus.REJECTED
        self.session.flush()
        return refund

    def cancel_subscription(self, subscription_id: int) -> Subscription:
        """Schedule cancellation at period end; repeating the call changes nothing."""
        sub = self.get_subscription(subscription_id)
        if sub.status == SubscriptionStatus.CANCELLED:
            raise InvalidRequestError("subscription is already cancelled")
        sub.cancel_at_period_end = True
        self.session.flush()
        return sub

    def _get[T](self, model: type[T], pk: int) -> T:
        obj = self.session.get(model, pk)
        if obj is None:
            raise NotFoundError(f"{model.__name__.lower()} {pk} not found")
        return obj

    def _resolve_target(
        self, target: RefundTarget, target_id: int
    ) -> tuple[Order | None, Invoice | None]:
        if target == RefundTarget.ORDER:
            return self.get_order(target_id), None
        return None, self.get_invoice(target_id)

    def _has_earlier_duplicate(self, invoice: Invoice) -> bool:
        if invoice.subscription_id is None:
            return False
        stmt = select(Invoice.id).where(
            Invoice.subscription_id == invoice.subscription_id,
            Invoice.id < invoice.id,
            Invoice.status.in_((InvoiceStatus.PAID, InvoiceStatus.REFUNDED)),
            Invoice.amount_cents == invoice.amount_cents,
            Invoice.issued_at >= invoice.issued_at - DUPLICATE_CHARGE_WINDOW,
            Invoice.issued_at <= invoice.issued_at,
        )
        return self.session.scalar(stmt.limit(1)) is not None

    def _apply_processed(self, refund: Refund) -> None:
        refunded = sum(
            r.amount_cents
            for r in (refund.order or refund.invoice).refunds
            if r.status in ACTIVE_REFUND_STATUSES
        )
        if refund.order is not None:
            full = refunded >= refund.order.total_cents
            refund.order.status = OrderStatus.REFUNDED if full else OrderStatus.PARTIALLY_REFUNDED
        elif refund.invoice is not None and refunded >= refund.invoice.amount_cents:
            refund.invoice.status = InvoiceStatus.REFUNDED
        self.session.flush()


def _same_request(refund: Refund, target: RefundTarget, target_id: int, amount_cents: int) -> bool:
    matches_target = (
        refund.order_id == target_id
        if target == RefundTarget.ORDER
        else refund.invoice_id == target_id
    )
    return matches_target and refund.amount_cents == amount_cents
