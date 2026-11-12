from typing import Any

from parley.evals.agent_eval import build_report
from parley.evals.compare import render_comparison
from parley.evals.scoring import ScenarioOutcome
from tests.test_eval_report import outcome


def report(arch: str, runs: list[list[ScenarioOutcome]]) -> dict[str, Any]:
    flat = [o for run in runs for o in run]
    return build_report(flat, "m", {"arch": arch, "repeats": len(runs)}, runs)


def test_comparison_puts_both_architectures_side_by_side() -> None:
    single = report("single", [[outcome("A"), outcome("B", state_ok=False)]] * 3)
    routed = outcome("A").model_copy(update={"specialist": "billing"})
    multi = report(
        "multi", [[routed, outcome("B").model_copy(update={"specialist": "billing"})]] * 3
    )
    text = render_comparison(single, multi)
    lines = text.splitlines()
    assert lines[0] == "| Metric | Single agent | Multi-agent |"
    row = next(line for line in lines if line.startswith("| Task success"))
    assert "50.0%" in row and "100.0%" in row
    pass_row = next(line for line in lines if "pass^3" in line)
    assert pass_row.endswith("| 50.0% | 100.0% |")
    router_row = next(line for line in lines if line.startswith("| Router"))
    assert "n/a" in router_row


def test_a_single_run_report_has_no_pass_all() -> None:
    single = report("single", [[outcome("A")]])
    multi = report("multi", [[outcome("A")]])
    text = render_comparison(single, multi)
    assert "(pass^1) | n/a | n/a" in text
