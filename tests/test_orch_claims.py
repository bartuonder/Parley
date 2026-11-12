import pytest

from parley.orchestration.claims import Claim, detect_claims, unbacked_claims


@pytest.mark.parametrize(
    "reply",
    [
        "We have processed the refund for the charger. You will receive $29.00 back.",
        "Your refund of $49.00 has been processed.",
        "Your order has been fully refunded today for $32.00 as you requested.",
        "I am processing the refund for you now.",
        "We have refunded you the full amount.",
    ],
)
def test_completed_refund_statements_are_claims(reply: str) -> None:
    assert detect_claims(reply) == {Claim.REFUND}


@pytest.mark.parametrize(
    "reply",
    [
        "The invoice you mentioned has already been refunded.",
        "Unfortunately the second charge cannot be refunded.",
        "Only invoices issued within 24 hours of each other qualify for a refund.",
        "Once approved, the refund will be processed.",
        "Your refund is pending approval.",
        "If eligible, we would refund the full amount.",
    ],
)
def test_refund_talk_that_is_not_a_completed_action_is_ignored(reply: str) -> None:
    assert detect_claims(reply) == set()


def test_cancellation_claims_are_first_person_only() -> None:
    assert detect_claims("It has not yet shipped, so I have canceled it for you.") == {Claim.CANCEL}
    assert detect_claims("We successfully cancelled your plan.") == {Claim.CANCEL}
    assert detect_claims("Your order 25 was cancelled before dispatch.") == set()
    assert detect_claims("Orders cannot be cancelled once shipped.") == set()


@pytest.mark.parametrize(
    "reply",
    [
        "I have escalated your case to a human agent.",
        "I have forwarded your request to the account team.",
        "A human specialist will follow up with you shortly.",
    ],
)
def test_handover_statements_are_claims(reply: str) -> None:
    assert detect_claims(reply) == {Claim.HANDOVER}


def test_claims_are_checked_against_what_was_executed() -> None:
    reply = "I have processed the refund. A human will follow up."
    both = unbacked_claims(reply, refunded=False, cancelled=False, handed_over=False)
    assert both == {Claim.REFUND, Claim.HANDOVER}
    assert unbacked_claims(reply, refunded=True, cancelled=False, handed_over=True) == set()
    assert unbacked_claims(reply, refunded=True, cancelled=False, handed_over=False) == {
        Claim.HANDOVER
    }
