import asyncio
import json

import pytest

from parley.db.enums import RefundStatus
from parley.evals.judge import CRITERIA, describe_happened, judge_outcomes, judge_reply
from parley.evals.loader import load_scenarios
from parley.evals.report import render_markdown, summarize
from parley.evals.schema import NewRefund, StateDiff
from parley.evals.scoring import ScenarioOutcome, TraceEntry
from tests.fakes import ScriptedLLM, reply_turn
from tests.test_eval_report import outcome


def verdict_json(**overrides: bool) -> str:
    passes = {name: overrides.get(name, True) for name in CRITERIA}
    return json.dumps({n: {"pass": ok, "reason": f"{n} reason"} for n, ok in passes.items()})


def graded(scenario_id: str = "A", reply: str = "Hello.") -> ScenarioOutcome:
    return outcome(scenario_id).model_copy(update={"reply": reply, "ticket_text": "Subject\nBody"})


def test_a_readable_verdict_carries_every_criterion_and_the_cost() -> None:
    llm = ScriptedLLM([reply_turn(verdict_json(no_leak=False), cost_usd=0.01)])
    verdict = asyncio.run(judge_reply(llm, "ticket", "Nothing was changed.", ["a fact"], "reply"))
    assert verdict is not None
    assert verdict.passes["no_leak"] is False and verdict.passes["facts_covered"] is True
    assert verdict.reasons["professional_tone"] == "professional_tone reason"
    assert verdict.usage.cost_usd == 0.01
    content = llm.requests[0][1]["content"]
    assert "- a fact" in content and "Nothing was changed." in content and "reply" in content


def test_an_unreadable_or_incomplete_verdict_is_not_a_grade() -> None:
    partial = json.dumps({"facts_covered": {"pass": True, "reason": ""}})
    for text in ("looks good", "{}", partial, '{"facts_covered": {"pass": "yes"}}'):
        llm = ScriptedLLM([reply_turn(text), reply_turn(text)])
        assert asyncio.run(judge_reply(llm, "t", "h", [], "r")) is None


def test_one_unreadable_answer_is_retried_and_both_calls_are_priced() -> None:
    llm = ScriptedLLM(
        [reply_turn("oops", cost_usd=0.01), reply_turn(verdict_json(), cost_usd=0.02)]
    )
    verdict = asyncio.run(judge_reply(llm, "t", "h", [], "r"))
    assert verdict is not None and verdict.usage.cost_usd == pytest.approx(0.03)


def test_the_record_of_what_happened_is_built_from_the_scored_outcome() -> None:
    quiet = outcome("A")
    assert describe_happened(quiet) == "Nothing was changed and no handover was made."
    busy = quiet.model_copy(
        update={
            "actual_diff": StateDiff(
                new_refunds=[
                    NewRefund(target="o1", amount_cents=25000, status=RefundStatus.PENDING_APPROVAL)
                ]
            ),
            "trace": [
                TraceEntry(name="escalate_to_human", arguments={"reason": "other"}, ok=True),
                TraceEntry(
                    name="issue_refund", arguments={}, ok=False, error_code="refund_not_allowed"
                ),
            ],
        }
    )
    text = describe_happened(busy)
    assert "250.00 on o1 is waiting for human approval" in text
    assert "handed over to a human (other)" in text and "refused (refund_not_allowed)" in text


def test_outcomes_are_graded_with_the_scenario_facts_and_empty_replies_are_skipped() -> None:
    scenario = next(s for s in load_scenarios() if s.id == "REF-001")
    llm = ScriptedLLM([reply_turn(verdict_json(professional_tone=False))])
    outcomes = [graded("REF-001"), graded("REF-002", reply="")]
    result = asyncio.run(judge_outcomes(llm, outcomes, [scenario]))
    assert result[0].judge is not None and result[0].judge["professional_tone"] is False
    assert result[0].judge_cost_usd == 0.001
    assert result[1].judge is None
    assert scenario.expected.reply_facts[0] in llm.requests[0][1]["content"]


def test_an_ungradable_reply_keeps_its_outcome_without_a_verdict() -> None:
    llm = ScriptedLLM([reply_turn("no"), reply_turn("still no")])
    result = asyncio.run(judge_outcomes(llm, [graded()], []))
    assert result[0].judge is None and result[0].reply == "Hello."


def test_pass_rates_are_summarized_per_criterion_over_graded_replies_only() -> None:
    good = graded("A").model_copy(update={"judge": dict.fromkeys(CRITERIA, True)})
    bad = graded("B").model_copy(
        update={"judge": {**dict.fromkeys(CRITERIA, True), "no_leak": False}}
    )
    summary = summarize([good, bad, graded("C")])
    assert summary.judge_pass_rates is not None
    assert (
        summary.judge_pass_rates["no_leak"] == 0.5
        and summary.judge_pass_rates["facts_covered"] == 1.0
    )
    assert "| Judge: no leak | 50.0% |" in render_markdown([good, bad], "m")
    assert summarize([graded("D")]).judge_pass_rates is None


def test_a_verdict_that_says_fail_instead_of_pass_is_understood() -> None:
    text = json.loads(verdict_json())
    text["no_leak"] = {"fail": True, "reason": "names another customer"}
    verdict = asyncio.run(
        judge_reply(ScriptedLLM([reply_turn(json.dumps(text))]), "t", "h", [], "r")
    )
    assert verdict is not None and verdict.passes["no_leak"] is False
    assert verdict.passes["facts_covered"] is True
