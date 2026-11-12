import asyncio

import pytest

from parley.agent.result import ToolInvocation
from parley.agent.ticket import Ticket
from parley.orchestration.critic import (
    CRITIC_PROMPT,
    LEGAL_THREAT,
    Verdict,
    render_evidence,
    review,
    rule_issues,
)
from parley.tools.context import Proposal
from tests.fakes import ScriptedLLM, reply_turn


def ticket(body: str) -> Ticket:
    return Ticket(id="T-1", sender_email="ada@example.com", subject="Order", body=body)


REFUND = Proposal(
    "issue_refund", {"target": "order", "target_id": 3, "amount_cents": 3200, "reason": "late"}
)
HANDOVER = Proposal("escalate_to_human", {"reason": "legal_threat", "summary": "lawyer"})


@pytest.mark.parametrize(
    "text",
    [
        "I will contact my lawyer and the consumer authority.",
        "I am going to sue you",
        "Expect a letter from my solicitor",
        "I will tell the press",
        "I will report this to the ombudsman",
        "See you in court",
    ],
)
def test_legal_threats_are_recognised(text: str) -> None:
    assert LEGAL_THREAT.search(text)


@pytest.mark.parametrize(
    "text", ["Please refund my order", "The court shoes I bought are too small", "I pressed pay"]
)
def test_ordinary_text_is_not_a_legal_threat(text: str) -> None:
    assert not LEGAL_THREAT.search(text)


def test_legal_threat_needs_a_handover_and_nothing_else() -> None:
    legal = ticket("Refund today or I call my lawyer.")
    assert rule_issues(legal, [HANDOVER]) == []
    missing = rule_issues(legal, [])
    assert len(missing) == 1 and "propose_escalation" in missing[0]
    both = rule_issues(legal, [REFUND, HANDOVER])
    assert len(both) == 1 and "only the handover" in both[0]
    assert rule_issues(ticket("Please refund order 3."), [REFUND]) == []


def test_rule_failures_skip_the_model_call() -> None:
    llm = ScriptedLLM([])
    verdict = asyncio.run(review(llm, ticket("I will sue"), [REFUND], "Refund coming.", []))
    assert not verdict.approved and verdict.source == "rules" and llm.requests == []
    assert verdict.feedback().startswith("Reviewer feedback")


def test_model_verdict_is_parsed_with_usage() -> None:
    answer = '```json\n{"approved": false, "issues": ["Window expired."]}\n```'
    llm = ScriptedLLM([reply_turn(answer, cost_usd=0.002)])
    verdict = asyncio.run(review(llm, ticket("Refund please"), [REFUND], "Done.", []))
    assert not verdict.approved and verdict.issues == ["Window expired."]
    assert verdict.usage.cost_usd == pytest.approx(0.002)
    system, user = llm.requests[0]
    assert system["content"] == CRITIC_PROMPT
    assert "Proposed actions" in user["content"] and "Draft reply:\nDone." in user["content"]


def test_approval_without_issues_and_unusable_answers() -> None:
    ok = asyncio.run(
        review(
            ScriptedLLM([reply_turn('{"approved": true, "issues": []}')]), ticket("x"), [], "", []
        )
    )
    assert ok.approved and ok.source == "llm"
    odd = asyncio.run(
        review(ScriptedLLM([reply_turn("looks fine to me")]), ticket("x"), [], "", [])
    )
    assert odd.approved and odd.source == "unparsed"
    empty = asyncio.run(
        review(
            ScriptedLLM([reply_turn('{"approved": false, "issues": []}')]), ticket("x"), [], "", []
        )
    )
    assert empty.approved


def test_evidence_is_compact_and_truncated() -> None:
    calls = [
        ToolInvocation(
            name="get_order", arguments={"order_id": 3}, ok=True, output={"a": "x" * 50}
        ),
        ToolInvocation(
            name="get_order",
            arguments={"order_id": 9},
            ok=False,
            output={"error_code": "not_found"},
        ),
    ]
    text = render_evidence(calls, limit=20)
    assert 'get_order({"order_id": 3}) -> ' in text and "error" in text
    assert len(text.splitlines()[0]) < 80


def test_verdict_feedback_lists_each_issue() -> None:
    feedback = Verdict(approved=False, issues=["A", "B"]).feedback()
    assert "- A" in feedback and "- B" in feedback
