import asyncio

import pytest

from parley.agent.ticket import Ticket
from parley.orchestration.executor import ExecutedAction
from parley.orchestration.responder import (
    RESPONDER_PROMPT,
    backing,
    money,
    render_facts,
    respond,
)
from tests.fakes import ScriptedLLM, reply_turn

TICKET = Ticket(id="T-1", sender_email="ada@example.com", subject="Refund", body="Refund please")


def refund(amount: int = 4900, ok: bool = True, approval: bool = False) -> ExecutedAction:
    return ExecutedAction(
        kind="issue_refund",
        arguments={"target": "order", "target_id": 7, "amount_cents": amount, "reason": "late"},
        ok=ok,
        output={"awaiting_approval": approval},
        error_code=None if ok else "not_eligible",
    )


HANDOVER = ExecutedAction(
    kind="escalate_to_human",
    arguments={"reason": "legal_threat", "summary": "Mentions a lawyer"},
    ok=True,
)


def test_money_is_formatted_in_currency_units() -> None:
    assert money(4900) == "$49.00" and money(123456) == "$1,234.56"


def test_facts_describe_what_really_happened() -> None:
    assert render_facts([]) == "- No action was taken."
    assert "was processed" in render_facts([refund()])
    assert "waiting for human approval, not paid yet" in render_facts([refund(approval=True)])
    failed = render_facts([refund(ok=False)])
    assert "could not be made: not_eligible" in failed
    handed = render_facts([HANDOVER])
    assert "A human agent will follow up" in handed and "Mentions a lawyer" in handed


def test_backing_counts_only_successful_actions_and_pending_approvals() -> None:
    assert backing([refund(ok=False)]) == {
        "refunded": False,
        "cancelled": False,
        "handed_over": False,
    }
    assert backing([refund(approval=True)])["handed_over"] is True
    assert backing([HANDOVER])["handed_over"] is True


def test_clean_reply_is_returned_after_one_call() -> None:
    llm = ScriptedLLM([reply_turn("Your refund of $49.00 was processed.", cost_usd=0.001)])
    final = asyncio.run(respond(llm, TICKET, "draft", [refund()]))
    assert final.text.startswith("Your refund") and not final.retried and final.unbacked == []
    system, user = llm.requests[0]
    assert system["content"] == RESPONDER_PROMPT
    assert "FACTS:\n- Refund of $49.00 for order 7 was processed." in user["content"]
    assert "Specialist draft:\ndraft" in user["content"]


def test_unbacked_claim_triggers_one_rewrite() -> None:
    llm = ScriptedLLM(
        [
            reply_turn("I have processed the refund for you.", cost_usd=0.001),
            reply_turn("The order is outside the return window, so no refund is possible.", 0.001),
        ]
    )
    final = asyncio.run(respond(llm, TICKET, "outside window", []))
    assert final.retried and final.unbacked == []
    assert final.text.startswith("The order is outside")
    assert final.usage.cost_usd == pytest.approx(0.002)
    assert "claims actions that FACTS does not list (refund)" in llm.requests[1][-1]["content"]


def test_a_claim_that_survives_the_rewrite_is_reported() -> None:
    llm = ScriptedLLM([reply_turn("I have refunded you."), reply_turn("We have refunded you.")])
    final = asyncio.run(respond(llm, TICKET, "", []))
    assert final.retried and final.unbacked == ["refund"]
