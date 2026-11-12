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
    assert "propose_cancel_subscription" in names(Specialist.SUBSCRIPTION)
    assert "propose_cancel_subscription" not in names(Specialist.BILLING)
    assert "propose_cancel_subscription" not in names(Specialist.SHIPPING)
    assert {"propose_refund", "propose_escalation"} <= names(Specialist.SUBSCRIPTION)


@pytest.mark.parametrize("specialist", list(Specialist))
def test_prompt_is_filled_and_states_the_proposal_contract(specialist: Specialist) -> None:
    prompt = specialist_prompt(specialist, date(2026, 6, 1))
    assert f"You are a {specialist.value} specialist" in prompt
    assert "Today is 2026-06-01" in prompt and str(APPROVAL_THRESHOLD_CENTS) in prompt
    assert "never state that something is already done" in prompt
    assert "{" not in prompt and "}" not in prompt


def test_memory_is_included_only_when_present() -> None:
    plain = specialist_prompt(Specialist.BILLING, date(2026, 6, 1))
    with_memory = specialist_prompt(Specialist.BILLING, date(2026, 6, 1), "- refund denied twice")
    assert "earlier tickets" not in plain
    assert "earlier tickets" in with_memory and "- refund denied twice" in with_memory
    assert "treat it as insistence" in with_memory and "treat it as insistence" not in plain
