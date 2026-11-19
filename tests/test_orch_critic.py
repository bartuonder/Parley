import asyncio
from datetime import UTC, datetime, timedelta

import pytest

from parley.agent.result import ToolInvocation
from parley.agent.ticket import Ticket
from parley.orchestration.critic import (
    CRITIC_PROMPT,
    LEGAL_THREAT,
    Verdict,
    recent_refunds,
    render_evidence,
    review,
    rule_issues,
)
from parley.tools.context import Proposal
from parley.tools.proposals import CANCEL
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


def test_cancelling_several_plans_needs_a_plural_request() -> None:
    two = [
        Proposal(CANCEL, {"subscription_id": 1}),
        Proposal(CANCEL, {"subscription_id": 2}),
    ]
    vague = Ticket(id="T", sender_email="a@x.io", subject="Cancel", body="Please cancel my plan.")
    plural = Ticket(id="T", sender_email="a@x.io", subject="Cancel", body="Cancel both plans.")
    assert any("which plan" in i for i in rule_issues(vague, two))
    assert rule_issues(plural, two) == []
    assert rule_issues(vague, two[:1]) == []
    assert rule_issues(vague, [two[0], Proposal(CANCEL, {"subscription_id": 1})]) == []


NOW_FOR_FRAUD = datetime(2026, 6, 1, 12, tzinfo=UTC)


def overview_with_refunds(*days_ago: int, status: str = "processed") -> ToolInvocation:
    refunds = [
        {
            "id": n,
            "amount_cents": 1000,
            "status": status,
            "created_at": (NOW_FOR_FRAUD - timedelta(days=d)).isoformat(),
        }
        for n, d in enumerate(days_ago, start=1)
    ]
    return ToolInvocation(
        name="get_customer_overview",
        arguments={},
        ok=True,
        output={"orders": [{"id": 1, "refunds": refunds}], "invoices": []},
    )


def refund_proposal() -> Proposal:
    return Proposal(
        "issue_refund", {"target": "order", "target_id": 3, "amount_cents": 500, "reason": "x"}
    )


def test_refunds_in_the_last_thirty_days_are_counted_once_each() -> None:
    call = overview_with_refunds(5, 20, 29, 45)
    assert recent_refunds([call, call], NOW_FOR_FRAUD) == 3
    assert recent_refunds([overview_with_refunds(5, status="rejected")], NOW_FOR_FRAUD) == 0
    failed = call.model_copy(update={"ok": False})
    assert recent_refunds([failed], NOW_FOR_FRAUD) == 0


def test_a_third_refund_in_a_month_must_go_to_a_human_instead() -> None:
    vague = Ticket(id="T", sender_email="a@x.io", subject="Refund", body="It never arrived.")
    calls = [overview_with_refunds(25, 9)]
    issues = rule_issues(vague, [refund_proposal()], calls, NOW_FOR_FRAUD)
    assert len(issues) == 1 and "POL-ESC-002" in issues[0] and "2 refunds" in issues[0]
    assert rule_issues(vague, [refund_proposal()], [overview_with_refunds(9)], NOW_FOR_FRAUD) == []
    assert rule_issues(vague, [], calls, NOW_FOR_FRAUD) == []
    assert rule_issues(vague, [refund_proposal()], calls) == []


def test_the_pattern_is_rejected_without_asking_the_model() -> None:
    llm = ScriptedLLM([])
    ticket = Ticket(id="T", sender_email="a@x.io", subject="Refund", body="Again.")
    verdict = asyncio.run(
        review(
            llm,
            ticket,
            [refund_proposal()],
            "Draft",
            [overview_with_refunds(25, 9)],
            now=NOW_FOR_FRAUD,
        )
    )
    assert not verdict.approved and verdict.source == "rules" and llm.requests == []


def test_the_critic_is_told_not_to_list_correct_points_or_ask_for_rewording() -> None:
    from parley.orchestration.critic import CRITIC_PROMPT

    assert "Never list a point that is already correct" in CRITIC_PROMPT
    assert "never ask for different wording" in CRITIC_PROMPT


def test_the_critic_sees_a_whole_customer_overview_of_ordinary_size() -> None:
    items = [{"order_id": n, "items": [f"item {n}"]} for n in range(120)]
    call = ToolInvocation(name="get_customer_overview", arguments={}, ok=True, output={"o": items})
    assert "item 119" in render_evidence([call])
