import pytest

from parley.evals.report import (
    group_by,
    percentile,
    render_markdown,
    render_repeats,
    summarize,
    summarize_repeats,
)
from parley.evals.schema import StateDiff
from parley.evals.scoring import ScenarioOutcome


def outcome(
    scenario_id: str = "REF-001",
    category: str = "refund",
    state_ok: bool = True,
    replied: bool = True,
    attempts: list[str] | None = None,
    handover: tuple[bool, bool] = (False, False),
    cost: float = 0.01,
    latency: float = 2.0,
    recall: float | None = None,
    error: str | None = None,
    calls: list[str] | None = None,
    tool_errors: int = 0,
) -> ScenarioOutcome:
    return ScenarioOutcome(
        scenario_id=scenario_id,
        category=category,
        difficulty="easy",
        tags=[],
        state_ok=state_ok,
        forbidden_attempts=attempts or [],
        handover_expected=handover[0],
        handover_actual=handover[1],
        replied=replied,
        policy_recall=recall,
        stop_reason="reply",
        steps=3,
        tool_calls=calls or ["get_order", "issue_refund"],
        tool_errors=tool_errors,
        cost_usd=cost,
        latency_s=latency,
        prompt_tokens=100,
        completion_tokens=20,
        reply="ok",
        actual_diff=StateDiff(),
        error=error,
    )


def test_percentile_uses_nearest_rank() -> None:
    values = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    assert percentile(values, 0.5) == 5.0 and percentile(values, 0.95) == 10.0
    assert percentile([], 0.5) == 0.0


def test_summary_rates_and_means() -> None:
    outcomes = [
        outcome("A", recall=1.0),
        outcome("B", state_ok=False, attempts=["issue_refund order o1"], tool_errors=1),
        outcome("C", handover=(True, False), recall=0.5, cost=0.03),
        outcome("D", replied=False),
    ]
    s = summarize(outcomes)
    assert s.n == 4 and s.success_rate == 0.5 and s.state_ok_rate == 0.75
    assert s.forbidden_attempt_rate == 0.25 and s.handover_accuracy == 0.75
    assert s.mean_policy_recall == 0.75
    assert s.tool_error_rate == 1 / 8
    assert round(s.total_cost_usd, 2) == 0.06 and round(s.mean_cost_usd, 3) == 0.015


def test_crashed_runs_count_as_errors_and_not_success() -> None:
    s = summarize([outcome(error="RuntimeError: api down", state_ok=False, replied=False)])
    assert s.error_rate == 1.0 and s.success_rate == 0.0


def test_empty_run_summarizes_to_zeros() -> None:
    s = summarize([])
    assert s.n == 0 and s.success_rate == 0.0 and s.mean_policy_recall is None


def test_grouping_and_markdown() -> None:
    outcomes = [outcome("A"), outcome("B", category="billing", state_ok=False)]
    groups = group_by(outcomes, lambda o: o.category)
    assert list(groups) == ["billing", "refund"] and groups["billing"].success_rate == 0.0
    text = render_markdown(outcomes, "test-model")
    assert "`test-model`" in text and "| refund | 1 | 100% |" in text
    assert "Failed: B" in text


def test_unbacked_claims_and_router_accuracy_are_summarized() -> None:
    routed_right = outcome("A", category="shipping").model_copy(update={"specialist": "shipping"})
    routed_wrong = outcome("B", category="billing").model_copy(
        update={"specialist": "shipping", "unbacked_claims": ["refund"], "revisions": 2}
    )
    s = summarize([routed_right, routed_wrong])
    assert s.router_accuracy == 0.5 and s.unbacked_claim_rate == 0.5 and s.mean_revisions == 1.0
    assert summarize([outcome("C")]).router_accuracy is None
    text = render_markdown([routed_right, routed_wrong], "m")
    assert "Reply claims an action that did not happen | 50.0%" in text
    assert "Router picked the expected specialist | 50.0%" in text


def test_repeat_summary_reports_variance_and_pass_all() -> None:
    run1 = [outcome("A"), outcome("B"), outcome("C", state_ok=False)]
    run2 = [outcome("A"), outcome("B", state_ok=False), outcome("C", state_ok=False)]
    run3 = [outcome("A"), outcome("B"), outcome("C", state_ok=False)]
    r = summarize_repeats([run1, run2, run3])
    assert r.runs == 3
    assert r.success_min == pytest.approx(1 / 3) and r.success_max == pytest.approx(2 / 3)
    assert r.success_mean == pytest.approx(5 / 9)
    assert r.pass_all == pytest.approx(1 / 3) and r.pass_any == pytest.approx(2 / 3)
    assert r.unstable == ["B"]


def test_repeat_summary_renders_a_readable_line() -> None:
    runs = [[outcome("A"), outcome("B")], [outcome("A"), outcome("B", state_ok=False)]]
    text = render_repeats(summarize_repeats(runs))
    assert "2 runs" in text and "pass^2" in text and "Unstable scenarios: B" in text
