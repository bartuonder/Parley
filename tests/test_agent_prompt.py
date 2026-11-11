from datetime import date

from parley.agent.llm import Usage
from parley.agent.prompt import render_ticket, system_prompt
from parley.agent.result import AgentResult, StopReason, ToolInvocation
from parley.backend.rules import APPROVAL_THRESHOLD_CENTS


def test_system_prompt_carries_the_date_and_the_approval_threshold() -> None:
    prompt = system_prompt(date(2026, 6, 1))
    assert "Today is 2026-06-01" in prompt
    assert str(APPROVAL_THRESHOLD_CENTS) in prompt
    assert "{" not in prompt and "}" not in prompt


def test_system_prompt_requires_an_overview_first_and_actions_to_match_words() -> None:
    prompt = system_prompt(date(2026, 6, 1))
    assert "call get_customer_overview" in prompt
    assert "the matching tool call must have succeeded first" in prompt


def test_ticket_body_is_fenced_as_data() -> None:
    text = render_ticket("T-1", "ada@example.com", "Refund", "Please help")
    assert text.startswith("Ticket T-1\nFrom: ada@example.com\nSubject: Refund")
    assert "<ticket_body>\nPlease help\n</ticket_body>" in text


def test_cited_policies_come_from_the_reply_and_policy_search() -> None:
    result = AgentResult(
        ticket_id="T-1",
        model="m",
        reply="Under POL-REF-001@v2 the window is 30 days.",
        stop_reason=StopReason.REPLY,
        steps=2,
        latency_s=0.1,
        usage=Usage(),
        tool_calls=[
            ToolInvocation(
                name="search_policies",
                arguments={"query": "window"},
                ok=True,
                output={"passages": [{"citation": "POL-GEN-003@v1 / Scope"}]},
            ),
            ToolInvocation(name="get_order", arguments={}, ok=True, output={"id": 1}),
        ],
    )
    assert result.cited_policies == ["POL-REF-001@v2", "POL-GEN-003@v1"]
