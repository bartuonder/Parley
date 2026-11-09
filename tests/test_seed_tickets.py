import re

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from parley.db.enums import RefundStatus, TicketOutcome
from parley.db.models import Ticket
from parley.policies.loader import load_policies
from parley.seed.config import REFERENCE_NOW

PLACEHOLDER = re.compile(r"[{}]|\bNone\b")


def test_ticket_volume(seeded: Session) -> None:
    assert (seeded.scalar(select(func.count()).select_from(Ticket)) or 0) >= 500


def test_text_has_no_unrendered_placeholders(seeded: Session) -> None:
    for t in seeded.scalars(select(Ticket)):
        for text in (t.subject, t.body, t.resolution):
            assert not PLACEHOLDER.search(text), (t.id, text)


def test_timestamps_are_ordered_and_not_in_the_future(seeded: Session) -> None:
    for t in seeded.scalars(select(Ticket)):
        assert t.customer.created_at <= t.created_at <= t.resolved_at <= REFERENCE_NOW
        if t.order is not None:
            assert t.order.placed_at <= t.created_at
        if t.invoice is not None:
            assert t.invoice.issued_at <= t.created_at


def test_policy_refs_point_to_versions_in_force_at_ticket_time(seeded: Session) -> None:
    docs = {d.key: d for d in load_policies()}
    for t in seeded.scalars(select(Ticket)):
        assert t.policy_refs
        for key in t.policy_refs:
            doc = docs[key]
            day = t.created_at.date()
            assert doc.effective_date <= day
            assert doc.expires_date is None or doc.expires_date >= day


def test_refunded_tickets_match_processed_refunds(seeded: Session) -> None:
    refunded = seeded.scalars(select(Ticket).where(Ticket.outcome == TicketOutcome.REFUNDED))
    for t in refunded:
        target = t.order or t.invoice
        assert target is not None
        assert any(r.status == RefundStatus.PROCESSED for r in target.refunds)


def test_denied_tickets_have_no_processed_refund(seeded: Session) -> None:
    for t in seeded.scalars(select(Ticket).where(Ticket.outcome == TicketOutcome.DENIED)):
        assert t.order is not None
        assert all(r.status != RefundStatus.PROCESSED for r in t.order.refunds)


def test_ticket_ids_are_chronological(seeded: Session) -> None:
    rows = seeded.execute(select(Ticket.id, Ticket.created_at).order_by(Ticket.id)).all()
    times = [r.created_at for r in rows]
    assert times == sorted(times)
