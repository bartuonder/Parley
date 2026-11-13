import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from parley.settings import PROJECT_ROOT

BASELINE_PATH = PROJECT_ROOT / "reports" / "baseline.json"
SUITE_PATH = PROJECT_ROOT / "reports" / "eval_suite.json"

Metrics = dict[str, float | None]

Direction = Literal["min", "max"]


@dataclass(frozen=True)
class Rule:
    """A metric must not get worse than the baseline by more than `tolerance`."""

    direction: Direction
    tolerance: float
    relative: bool = False
    bound: float | None = None


# Tolerances sit above the run-to-run spread of the committed baselines (about 2 points).
RULES: dict[str, Rule] = {
    "success_rate": Rule("min", 0.05, bound=0.80),
    "pass_all": Rule("min", 0.08, bound=0.60),
    "policy_violation_rate": Rule("max", 0.02, bound=0.02),
    "unbacked_claim_rate": Rule("max", 0.02),
    "handover_accuracy": Rule("min", 0.05),
    "tool_precision": Rule("min", 0.05),
    "tool_recall": Rule("min", 0.05),
    "mean_cost_usd": Rule("max", 0.25, relative=True, bound=0.05),
}
JUDGE_RULE = Rule("min", 0.05)


@dataclass(frozen=True)
class Row:
    scope: str
    metric: str
    baseline: float | None
    current: float | None
    ok: bool
    reason: str = ""


@dataclass(frozen=True)
class GateResult:
    rows: list[Row]

    @property
    def failures(self) -> list[Row]:
        return [r for r in self.rows if not r.ok]

    @property
    def passed(self) -> bool:
        return not self.failures


def extract_metrics(report: dict[str, Any]) -> Metrics:
    """The gated numbers of one eval report."""
    summary = report["summary"]
    metrics: Metrics = {
        "success_rate": summary["success_rate"],
        "pass_all": report.get("repeats", {}).get("pass_all"),
        "policy_violation_rate": summary.get("policy_violation_rate"),
        "unbacked_claim_rate": summary["unbacked_claim_rate"],
        "handover_accuracy": summary["handover_accuracy"],
        "tool_precision": summary.get("tool_precision"),
        "tool_recall": summary.get("tool_recall"),
        "mean_cost_usd": summary["mean_cost_usd"],
    }
    for name, rate in (summary.get("judge_pass_rates") or {}).items():
        metrics[f"judge_{name}"] = rate
    return metrics


def _rule_for(metric: str) -> Rule | None:
    if metric.startswith("judge_"):
        return JUDGE_RULE
    return RULES.get(metric)


def _check_one(scope: str, metric: str, rule: Rule, base: float, now: float | None) -> Row:
    if now is None:
        return Row(scope, metric, base, None, False, "missing from the current run")
    slack = rule.tolerance * (abs(base) if rule.relative else 1.0)
    worse = now < base - slack if rule.direction == "min" else now > base + slack
    if worse:
        return Row(scope, metric, base, now, False, f"worse than baseline by more than {slack:.3g}")
    if rule.bound is not None:
        broken = now < rule.bound if rule.direction == "min" else now > rule.bound
        if broken:
            return Row(scope, metric, base, now, False, f"outside the target of {rule.bound:g}")
    return Row(scope, metric, base, now, True)


def check(current: dict[str, Metrics], baseline: dict[str, Metrics]) -> GateResult:
    """Compare every baseline scope and metric with the current run."""
    rows: list[Row] = []
    for scope, base_metrics in baseline.items():
        now_metrics = current.get(scope)
        for metric, base in base_metrics.items():
            rule = _rule_for(metric)
            if rule is None or base is None:
                continue
            if now_metrics is None:
                rows.append(Row(scope, metric, base, None, False, "scope missing from the run"))
                continue
            rows.append(_check_one(scope, metric, rule, base, now_metrics.get(metric)))
    return GateResult(rows)


def render_gate(result: GateResult) -> str:
    def fmt(value: float | None) -> str:
        return "n/a" if value is None else f"{value:.4g}"

    lines = [
        "| Scope | Metric | Baseline | Current | Result |",
        "| --- | --- | --- | --- | --- |",
    ]
    for r in result.rows:
        status = "ok" if r.ok else f"FAIL: {r.reason}"
        lines.append(
            f"| {r.scope} | {r.metric} | {fmt(r.baseline)} | {fmt(r.current)} | {status} |"
        )
    verdict = "Gate passed." if result.passed else f"Gate failed: {len(result.failures)} check(s)."
    return "\n".join(lines) + f"\n\n{verdict}\n"


def select_scopes(metrics: dict[str, Metrics], scopes: list[str]) -> dict[str, Metrics]:
    """Keep only the named scopes; an unknown scope is an error, not a silent gap."""
    unknown = sorted(set(scopes) - set(metrics))
    if unknown:
        raise SystemExit(f"scopes not in the run: {', '.join(unknown)}")
    return {scope: metrics[scope] for scope in scopes} if scopes else metrics


def load_metrics(path: Path) -> dict[str, Metrics]:
    data: dict[str, Metrics] = json.loads(path.read_text(encoding="utf-8"))["metrics"]
    return data


def main() -> None:
    parser = argparse.ArgumentParser(description="Fail when the eval suite got worse.")
    parser.add_argument("--current", type=Path, default=SUITE_PATH)
    parser.add_argument("--baseline", type=Path, default=BASELINE_PATH)
    parser.add_argument(
        "--update-baseline", action="store_true", help="accept the current run as the baseline"
    )
    parser.add_argument("--scopes", nargs="*", default=[], help="scopes to keep in the baseline")
    args = parser.parse_args()
    current = load_metrics(args.current)
    if args.update_baseline:
        kept = select_scopes(current, args.scopes)
        args.baseline.write_text(json.dumps({"metrics": kept}, indent=2) + "\n", "utf-8")
        print(f"baseline written to {args.baseline}")
        return
    result = check(current, load_metrics(args.baseline))
    print(render_gate(result))
    raise SystemExit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
