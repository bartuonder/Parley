from parley.evals.report import group_by, percentile, render_markdown, summarize
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
