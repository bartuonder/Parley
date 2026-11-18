from datetime import date

import pytest

from parley.backend.rules import APPROVAL_THRESHOLD_CENTS
from parley.orchestration.router import Specialist
from parley.orchestration.specialists import (
    SPECIALIST_TOOLS,
    specialist_prompt,
    specialist_registry,
)

WRITE_TOOLS = {"issue_refund", "cancel_subscription", "escalate_to_human"}


@pytest.mark.parametrize("specialist", list(Specialist))
def test_specialists_hold_no_direct_write_tool(specialist: Specialist) -> None:
    names = {s.name for s in specialist_registry(specialist).specs}
    assert names == SPECIALIST_TOOLS[specialist]
    assert not names & WRITE_TOOLS


def test_least_privilege_differs_per_specialist() -> None:
    def names(s: Specialist) -> set[str]:
        return {spec.name for spec in specialist_registry(s).specs}

    assert "get_shipment" in names(Specialist.SHIPPING)
    assert "get_shipment" not in names(Specialist.SUBSCRIPTION)
    assert "get_shipment" not in names(Specialist.BILLING)
    assert "get_order" not in names(Specialist.SUBSCRIPTION)
    assert {"propose_refund", "propose_escalation"} <= names(Specialist.SUBSCRIPTION)


@pytest.mark.parametrize("specialist", list(Specialist))
def test_every_specialist_can_propose_a_cancellation_for_mixed_requests(
    specialist: Specialist,
) -> None:
    names = {s.name for s in specialist_registry(specialist).specs}
    assert {"propose_cancel_subscription", "get_subscription"} <= names


@pytest.mark.parametrize("specialist", list(Specialist))
def test_prompt_is_filled_and_states_the_proposal_contract(specialist: Specialist) -> None:
    prompt = specialist_prompt(specialist, date(2026, 6, 1))
    assert f"You are a {specialist.value} specialist" in prompt
    assert "Today is 2026-06-01" in prompt and str(APPROVAL_THRESHOLD_CENTS) in prompt
    assert "never state that something is already done" in prompt
    assert "{" not in prompt and "}" not in prompt


def test_the_prompt_separates_denials_from_handovers_and_asks_when_a_request_is_ambiguous() -> None:
    prompt = specialist_prompt(Specialist.SHIPPING, date(2026, 6, 1))
    assert "explain the denial and propose no handover" in prompt
    assert "that is insistence, and it goes to a human" in prompt
    assert "that is insistence, and it goes to a human" in prompt
    assert "never work them out yourself" in prompt
    assert "ask which one in your final message and propose nothing yet" in prompt
    assert "annual plans cannot be paused" in specialist_prompt(
        Specialist.SUBSCRIPTION, date(2026, 6, 1)
    )


def test_memory_is_included_only_when_present() -> None:
    plain = specialist_prompt(Specialist.BILLING, date(2026, 6, 1))
    with_memory = specialist_prompt(Specialist.BILLING, date(2026, 6, 1), "- refund denied twice")
    assert "earlier tickets" not in plain
    assert "earlier tickets" in with_memory and "- refund denied twice" in with_memory
    assert "treat it as insistence" in with_memory and "treat it as insistence" not in plain


def test_the_prefix_a_provider_can_cache_is_the_same_for_every_ticket() -> None:
    first = specialist_prompt(Specialist.BILLING, date(2026, 6, 1))
    second = specialist_prompt(Specialist.BILLING, date(2026, 6, 1))
    assert first == second
    with_memory = specialist_prompt(Specialist.BILLING, date(2026, 6, 1), "- refund denied twice")
    shared = with_memory.index("What is known about this customer")
    assert with_memory[:shared] == first[:shared]
    schemas = [s.json_schema() for s in specialist_registry(Specialist.BILLING).specs]
    assert schemas == [s.json_schema() for s in specialist_registry(Specialist.BILLING).specs]


def test_with_a_prefetched_overview_the_prompt_says_it_is_already_there() -> None:
    plain = specialist_prompt(Specialist.BILLING, date(2026, 6, 1))
    ready = specialist_prompt(Specialist.BILLING, date(2026, 6, 1), prefetched=True)
    assert "then call get_customer_overview" in plain and "do not call it again" not in plain
    assert "do not call it again" in ready and "then call get_customer_overview" not in ready
    assert "{" not in ready and "}" not in ready


def test_the_prompt_keeps_large_refunds_and_clear_requests_out_of_handovers_and_questions() -> None:
    text = specialist_prompt(Specialist.BILLING, date(2026, 6, 1))
    assert "never propose a handover just because of its size" in text
    assert "do not ask the customer to confirm a request they have already made" in text
    assert "still propose what the sender is entitled to" in text
