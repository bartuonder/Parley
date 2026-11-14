from typing import Any

import pytest

from parley.evals import suite
from parley.evals.agent_eval import build_report
from parley.evals.gate import check
from parley.evals.suite import (
    Step,
    attack_breakdown,
    collect_metrics,
    full_plan,
    gate_plan,
    render_security_report,
    render_suite_report,
    report_cost,
    run_suite,
    security_plan,
    step_args,
)
from parley.security.guards import GUARD_NAMES
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
    assert scopes[:8] == [
        "single/core",
        "multi/core",
        "single/heldout",
        "multi/heldout",
        "single/dialogue",
        "multi/dialogue",
        "single/redteam",
        "multi/redteam",
    ]
    assert "multi-no_critic/core" in scopes and "multi-no_router/heldout" in scopes
    assert len(plan) == 14 and len(set(scopes)) == 14
    assert all(s.repeats == 4 for s in plan[:8])
    assert all(s.judge for s in plan[:6]) and not any(s.judge for s in plan[6:])
    assert all(s.repeats == 2 for s in plan[8:])


def test_the_gate_plan_runs_the_multi_agent_sets_and_the_red_team_set() -> None:
    plan = gate_plan(3)
    assert [s.scope for s in plan] == ["multi/core", "multi/heldout", "multi/redteam"]
    assert [s.judge for s in plan] == [True, True, False]
    assert all(s.repeats == 3 for s in plan)


def test_the_security_plan_compares_guards_off_and_on_then_switches_each_guard_off() -> None:
    plan = security_plan(repeats=3, ablation_repeats=1)
    scopes = [s.scope for s in plan]
    assert scopes[:4] == [
        "single-guards_off/redteam",
        "multi-guards_off/redteam",
        "single/redteam",
        "multi/redteam",
    ]
    assert scopes[4:] == [f"multi-guards_no_{name}/redteam" for name in GUARD_NAMES]
    assert all(s.repeats == 3 for s in plan[:4]) and all(s.repeats == 1 for s in plan[4:])
    assert not any(s.judge for s in plan)


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


def attack_report(success: list[bool], arch: str = "multi", guards: str = "on") -> dict[str, Any]:
    attacks = [
        outcome(f"A{i}").model_copy(
            update={
                "attack_success": hit,
                "attack_category": "direct_injection" if i % 2 == 0 else "exfiltration",
                "attack_split": "dev" if i < 2 else "test",
                "guard_events": ["injection:mode_switch"] if hit is False else [],
            }
        )
        for i, hit in enumerate(success)
    ]
    meta = {"arch": arch, "repeats": 1, "guards": guards}
    return build_report(attacks, "agent-model", meta)


def test_the_security_report_shows_asr_before_and_after_by_split_category_and_guard() -> None:
    reports = {
        "multi-guards_off/redteam": attack_report([True, True, True, False], guards="off"),
        "multi/redteam": attack_report([False, False, True, False]),
        "multi-guards_no_scan/redteam": attack_report([False, True, True, False]),
    }
    text = render_security_report(reports, cost_usd=1.5)
    assert "Cost of this run: $1.50" in text
    assert "| multi | off | 100.0% | 50.0% | 75.0% |" in text
    assert "| multi | on | 0.0% | 50.0% | 25.0% |" in text
    assert "| direct injection | 2 | 2/2 (100%) | 1/2 (50%) |" in text
    assert "| scan | 50.0% | 50.0% | 50.0% |" in text and "| none (all on) |" in text


def test_the_attack_breakdown_counts_attacks_and_successes_per_category() -> None:
    breakdown = attack_breakdown(attack_report([True, False, True, True]))
    assert breakdown == {"direct_injection": (2, 2), "exfiltration": (2, 1)}
