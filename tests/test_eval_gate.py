import json
from pathlib import Path

import pytest

from parley.evals.agent_eval import build_report
from parley.evals.gate import (
    BASELINE_PATH,
    Metrics,
    Row,
    check,
    extract_metrics,
    load_metrics,
    render_gate,
    select_scopes,
)
from tests.test_eval_report import outcome

BASE: dict[str, Metrics] = {
    "multi/core": {
        "success_rate": 0.95,
        "pass_all": 0.90,
        "policy_violation_rate": 0.0,
        "mean_cost_usd": 0.0026,
        "judge_no_leak": 1.0,
    }
}


def with_changes(**changes: float | None) -> dict[str, Metrics]:
    return {"multi/core": {**BASE["multi/core"], **changes}}


def failed(rows: list[Row]) -> list[str]:
    return [r.metric for r in rows if not r.ok]


def test_an_unchanged_run_passes() -> None:
    result = check(with_changes(), BASE)
    assert result.passed and len(result.rows) == 5


def test_small_noise_passes_and_a_real_drop_fails() -> None:
    assert check(with_changes(success_rate=0.92), BASE).passed
    result = check(with_changes(success_rate=0.85), BASE)
    assert failed(result.failures) == ["success_rate"]
    assert "worse than baseline" in result.failures[0].reason


def test_the_absolute_targets_hold_even_when_the_baseline_was_already_close() -> None:
    low: dict[str, Metrics] = {"multi/core": {"success_rate": 0.82}}
    result = check({"multi/core": {"success_rate": 0.79}}, low)
    assert failed(result.failures) == ["success_rate"] and "target" in result.failures[0].reason


def test_lower_is_better_metrics_fail_when_they_rise() -> None:
    assert failed(check(with_changes(policy_violation_rate=0.04), BASE).failures) == [
        "policy_violation_rate"
    ]
    assert failed(check(with_changes(mean_cost_usd=0.0040), BASE).failures) == ["mean_cost_usd"]
    assert check(with_changes(mean_cost_usd=0.0030), BASE).passed


def test_judge_rates_are_gated_and_missing_numbers_fail() -> None:
    assert failed(check(with_changes(judge_no_leak=0.90), BASE).failures) == ["judge_no_leak"]
    gone = check(with_changes(pass_all=None), BASE)
    assert failed(gone.failures) == ["pass_all"] and "missing" in gone.failures[0].reason
    assert not check({}, BASE).passed


def test_new_scopes_and_unknown_metrics_in_the_current_run_are_ignored() -> None:
    extra: dict[str, Metrics] = {**with_changes(), "single/core": {"success_rate": 0.1}}
    assert check(extra, BASE).passed
    assert check(with_changes(latency_p95_s=99.0), {"multi/core": {"latency_p95_s": 1.0}}).passed


def test_metrics_are_extracted_from_an_eval_report() -> None:
    runs = [[outcome("A")], [outcome("A", state_ok=False)]]
    flat = [o for run in runs for o in run]
    metrics = extract_metrics(build_report(flat, "m", {}, runs))
    assert metrics["success_rate"] == 0.5 and metrics["pass_all"] == 0.0
    assert metrics["policy_violation_rate"] == 0.0
    single = extract_metrics(build_report(runs[0], "m", {}))
    assert single["pass_all"] is None


def test_the_table_lists_failures_and_the_verdict() -> None:
    text = render_gate(check(with_changes(success_rate=0.5), BASE))
    assert "| multi/core | success_rate | 0.95 | 0.5 | FAIL:" in text
    assert "Gate failed: 1 check(s)." in text
    assert "Gate passed." in render_gate(check(with_changes(), BASE))


def test_the_committed_baseline_is_readable_when_present(tmp_path: Path) -> None:
    path = tmp_path / "baseline.json"
    path.write_text(json.dumps({"metrics": BASE}), encoding="utf-8")
    assert load_metrics(path) == BASE
    if BASELINE_PATH.exists():
        assert load_metrics(BASELINE_PATH)
    with pytest.raises(KeyError):
        path.write_text("{}", encoding="utf-8")
        load_metrics(path)


def test_a_baseline_can_keep_only_some_scopes_and_rejects_unknown_ones() -> None:
    both: dict[str, Metrics] = {**BASE, "single/core": {"success_rate": 0.9}}
    assert list(select_scopes(both, ["multi/core"])) == ["multi/core"]
    assert select_scopes(both, []) == both
    with pytest.raises(SystemExit, match="nope/core"):
        select_scopes(both, ["nope/core"])


def test_attack_success_is_gated_against_the_baseline_and_the_five_percent_target() -> None:
    base: dict[str, Metrics] = {"multi/redteam": {"attack_success_rate": 0.02}}
    assert check({"multi/redteam": {"attack_success_rate": 0.04}}, base).passed
    worse = check({"multi/redteam": {"attack_success_rate": 0.06}}, base)
    assert failed(worse.failures) == ["attack_success_rate"]
    assert check({"multi/core": {}}, {"multi/core": {"attack_success_rate": None}}).passed
