from typing import Any

import pytest

from parley.evals import suite
from parley.evals.agent_eval import build_report
from parley.evals.gate import check
from parley.evals.suite import (
    Step,
    collect_metrics,
    full_plan,
    gate_plan,
    render_suite_report,
    report_cost,
    run_suite,
    step_args,
)
from tests.test_eval_report import outcome


def make_report(arch: str = "multi", ablation: str | None = None, **update: Any) -> dict[str, Any]:
    routed = outcome("A").model_copy(update={"specialist": "billing", **update})
    runs = [[routed, outcome("B")], [routed, outcome("B")]]
    flat = [o for run in runs for o in run]
    meta = {"arch": arch, "repeats": 2, "router_model": "router", "ablation": ablation}
    return build_report(flat, "agent-model", meta, runs)


def test_the_full_plan_covers_every_set_for_both_architectures_and_each_ablation() -> None:
    plan = full_plan(repeats=4, ablation_repeats=2)
    scopes = [s.scope for s in plan]
    assert scopes[:6] == [
        "single/core",
        "multi/core",
        "single/heldout",
        "multi/heldout",
        "single/dialogue",
        "multi/dialogue",
    ]
    assert "multi-no_critic/core" in scopes and "multi-no_router/heldout" in scopes
    assert len(plan) == 12 and len(set(scopes)) == 12
    assert all(s.repeats == 4 and s.judge for s in plan[:6])
    assert all(s.repeats == 2 and not s.judge for s in plan[6:])


def test_the_gate_plan_runs_only_the_multi_agent_sets_with_the_judge() -> None:
    plan = gate_plan(3)
    assert [s.scope for s in plan] == ["multi/core", "multi/heldout"]
    assert all(s.judge and s.repeats == 3 for s in plan)


def test_a_step_becomes_eval_command_arguments() -> None:
    args = step_args(Step("multi", "heldout", 2, judge=False, ablate="critic"), budget=1.5)
    assert (args.arch, args.scenario_set, args.repeats) == ("multi", "heldout", 2)
    assert args.ablate == "critic" and args.judge is False and args.budget == 1.5
    assert step_args(Step("single", "core", 4), budget=3.0).judge is True


def test_the_cost_of_a_report_includes_the_simulator_and_the_judge() -> None:
    report = make_report(cost_usd=0.01, simulator_cost_usd=0.002, judge_cost_usd=0.003)
    assert report_cost(report) == pytest.approx(report["summary"]["total_cost_usd"] + 0.01)


def test_the_report_names_each_section_that_has_data() -> None:
    judged: dict[str, Any] = {"judge": dict.fromkeys(("facts_covered", "no_false_claims"), True)}
    reports = {
        "single/core": make_report("single"),
        "multi/core": make_report("multi", **judged),
        "multi-no_critic/core": make_report("multi", "critic"),
    }
    metrics = collect_metrics(reports)
    gate = check(metrics, {"multi/core": {"success_rate": 0.99}})
    calibration = {
        "model": "judge-model",
        "samples": 50,
        "criteria": [{"criterion": "no_leak", "agreement": 0.96, "kappa": 0.8}],
    }
    text = render_suite_report(reports, calibration, gate, cost_usd=1.234)
    assert "Cost of this run: $1.23" in text and "`agent-model`" in text
    assert "## Single agent against multi-agent: core set" in text
    assert "## Reply quality (LLM judge)" in text and "| multi/core |" in text
    assert "| Without the critic | core |" in text and "| Full multi-agent graph | core |" in text
    assert "no leak 96% (kappa 0.80)" in text and "50 labeled replies" in text
    assert "## Regression gate" in text
    assert "## Single agent against multi-agent: heldout set" not in text


def test_the_comparison_table_includes_policy_and_tool_accuracy() -> None:
    text = suite.render_comparison(make_report("single"), make_report("multi"))
    assert "Policy violation" in text and "(precision)" in text and "(recall)" in text


def test_a_suite_stops_when_its_budget_is_used_up(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[float] = []

    def fake_execute(args: Any) -> dict[str, Any]:
        calls.append(args.budget)
        report = make_report()
        report["summary"]["total_cost_usd"] = 0.6
        return report

    monkeypatch.setattr(suite, "execute", fake_execute)
    plan = [Step("multi", "core", 1), Step("multi", "heldout", 1), Step("single", "core", 1)]
    with pytest.raises(SystemExit, match="budget"):
        run_suite(plan, budget=1.0)
    assert calls == pytest.approx([1.0, 0.4])
    reports, spent = run_suite(plan[:1], budget=1.0)
    assert list(reports) == ["multi/core"] and spent == pytest.approx(0.6)
