import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from parley.evals.agent_eval import ABLATIONS, execute, parse_args
from parley.evals.attack import attack_attempted, attack_harm
from parley.evals.calibration import REPORT_PATH as CALIBRATION_PATH
from parley.evals.compare import render_comparison
from parley.evals.gate import (
    BASELINE_PATH,
    SUITE_PATH,
    GateResult,
    Metrics,
    check,
    extract_metrics,
    load_metrics,
    render_gate,
)
from parley.security.guards import GUARD_NAMES
from parley.settings import PROJECT_ROOT

REPORT_PATH = PROJECT_ROOT / "reports" / "eval_report.md"
MAIN_SETS = ("core", "heldout", "dialogue", "redteam")
ABLATION_SETS = ("core", "heldout")
SECURITY_REPORT_PATH = PROJECT_ROOT / "reports" / "security_report.md"
SECURITY_SUITE_PATH = PROJECT_ROOT / "reports" / "security_suite.json"


@dataclass(frozen=True)
class Step:
    arch: str
    scenario_set: str
    repeats: int
    judge: bool = True
    ablate: str | None = None
    guards: str = "on"

    @property
    def scope(self) -> str:
        name = self.arch + (f"-no_{self.ablate}" if self.ablate else "")
        name += "" if self.guards == "on" else f"-guards_{self.guards}"
        return f"{name}/{self.scenario_set}"


def full_plan(repeats: int, ablation_repeats: int) -> list[Step]:
    steps = [
        Step(arch, s, repeats, judge=s != "redteam")
        for s in MAIN_SETS
        for arch in ("single", "multi")
    ]
    steps += [
        Step("multi", s, ablation_repeats, judge=False, ablate=name)
        for name in sorted(ABLATIONS)
        for s in ABLATION_SETS
    ]
    return steps


def gate_plan(repeats: int) -> list[Step]:
    return [
        Step("multi", "core", repeats),
        Step("multi", "heldout", repeats),
        Step("multi", "redteam", repeats, judge=False),
    ]


def security_plan(repeats: int, ablation_repeats: int) -> list[Step]:
    """Attack success without and with the guards, then with one guard switched off at a time."""
    steps = [
        Step(arch, "redteam", repeats, judge=False, guards=setting)
        for setting in ("off", "on")
        for arch in ("single", "multi")
    ]
    steps += [
        Step("multi", "redteam", ablation_repeats, judge=False, guards=f"no_{name}")
        for name in GUARD_NAMES
    ]
    return steps


def step_args(step: Step, budget: float) -> argparse.Namespace:
    argv = ["--arch", step.arch, "--set", step.scenario_set, "--repeats", str(step.repeats)]
    argv += ["--budget", f"{budget:.4f}"]
    if step.judge:
        argv.append("--judge")
    if step.ablate:
        argv += ["--ablate", step.ablate]
    argv += ["--guards", step.guards]
    return parse_args(argv)


def report_cost(report: dict[str, Any]) -> float:
    extra = sum(
        o.get("simulator_cost_usd", 0.0) + o.get("judge_cost_usd", 0.0) for o in report["outcomes"]
    )
    return float(report["summary"]["total_cost_usd"]) + extra


def collect_metrics(reports: dict[str, dict[str, Any]]) -> dict[str, Metrics]:
    return {scope: extract_metrics(report) for scope, report in reports.items()}


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def _ablation_table(reports: dict[str, dict[str, Any]]) -> list[str]:
    configs = [("multi", "Full multi-agent graph")] + [
        (f"multi-no_{name}", label)
        for name, label in (
            ("critic", "Without the critic"),
            ("rewrite", "Without the reply rewrite"),
            ("router", "Without routing (always billing)"),
        )
    ]
    lines = [
        "| Configuration | Set | Success | pass^k | Handover | Unbacked claims | Cost / ticket |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for prefix, label in configs:
        for s in ABLATION_SETS:
            report = reports.get(f"{prefix}/{s}")
            if report is None:
                continue
            m = report["summary"]
            lines.append(
                f"| {label} | {s} | {_pct(m['success_rate'])} "
                f"| {_pct(report.get('repeats', {}).get('pass_all'))} "
                f"| {_pct(m['handover_accuracy'])} | {_pct(m['unbacked_claim_rate'])} "
                f"| ${m['mean_cost_usd']:.4f} |"
            )
    return lines


def _judge_table(reports: dict[str, dict[str, Any]]) -> list[str]:
    rows = [
        (scope, r["summary"]["judge_pass_rates"])
        for scope, r in reports.items()
        if r["summary"].get("judge_pass_rates")
    ]
    if not rows:
        return []
    names = list(rows[0][1])
    lines = [
        "| Scope | " + " | ".join(n.replace("_", " ") for n in names) + " |",
        "| --- |" + " --- |" * len(names),
    ]
    lines += [
        f"| {scope} | " + " | ".join(_pct(rates[n]) for n in names) + " |" for scope, rates in rows
    ]
    return lines


def render_suite_report(
    reports: dict[str, dict[str, Any]],
    calibration: dict[str, Any] | None,
    gate: GateResult | None,
    cost_usd: float,
) -> str:
    meta = next(
        (r["meta"] for r in reports.values() if r["meta"].get("router_model")),
        next(iter(reports.values()))["meta"],
    )
    lines = [
        "# Evaluation report",
        "",
        f"Generated {datetime.now(UTC):%Y-%m-%d %H:%M} UTC. Agent model `{meta['model']}`, "
        f"router `{meta.get('router_model') or 'n/a'}`. Cost of this run: ${cost_usd:.2f}.",
    ]
    for s in MAIN_SETS:
        single, multi = reports.get(f"single/{s}"), reports.get(f"multi/{s}")
        if single and multi:
            lines += ["", f"## Single agent against multi-agent: {s} set", ""]
            lines += [render_comparison(single, multi).rstrip()]
    judge = _judge_table(reports)
    if judge:
        lines += ["", "## Reply quality (LLM judge)", "", *judge]
    ablation = _ablation_table(reports)
    if len(ablation) > 2:
        lines += ["", "## Ablation of the multi-agent graph", "", *ablation]
    if calibration:
        lines += ["", "## Judge calibration", "", _calibration_line(calibration)]
    if gate is not None:
        lines += ["", "## Regression gate", "", render_gate(gate).rstrip()]
    return "\n".join(lines) + "\n"


def _calibration_line(calibration: dict[str, Any]) -> str:
    parts = [
        f"{c['criterion'].replace('_', ' ')} {c['agreement']:.0%} (kappa "
        f"{'n/a' if c['kappa'] is None else format(c['kappa'], '.2f')})"
        for c in calibration["criteria"]
    ]
    return (
        f"Judge `{calibration['model']}` against {calibration['samples']} labeled replies: "
        + ", ".join(parts)
        + ". Full table in `reports/judge_calibration.md`."
    )


def run_suite(steps: list[Step], budget: float) -> tuple[dict[str, dict[str, Any]], float]:
    reports: dict[str, dict[str, Any]] = {}
    spent = 0.0
    for step in steps:
        remaining = budget - spent
        if remaining <= 0:
            raise SystemExit(f"suite budget of {budget:.2f} USD reached before {step.scope}")
        print(f"=== {step.scope} (x{step.repeats})", flush=True)
        report = execute(step_args(step, remaining))
        reports[step.scope] = report
        spent += report_cost(report)
    return reports, spent


def _outcomes(report: dict[str, Any], split: str | None = None) -> list[dict[str, Any]]:
    return [
        o
        for o in report["outcomes"]
        if o.get("attack_success") is not None and (split is None or o["attack_split"] == split)
    ]


def _harm(o: dict[str, Any]) -> bool:
    """The attack landed; recomputed from stored fields so older reports read the same way."""
    return attack_harm(bool(o["unexpected_changes"]), o["leaked"], o["reply"])


def _manipulated(o: dict[str, Any]) -> bool:
    return attack_attempted(o["forbidden_attempts"], _harm(o))


def _rate(
    report: dict[str, Any] | None, split: str | None = None, manipulated: bool = False
) -> str:
    if report is None:
        return "n/a"
    attacks = _outcomes(report, split)
    if not attacks:
        return "n/a"
    test = _manipulated if manipulated else _harm
    return _pct(sum(1 for o in attacks if test(o)) / len(attacks))


def attack_breakdown(report: dict[str, Any]) -> dict[str, tuple[int, int, int]]:
    """Per attack category: attacks run, attacks that manipulated the agent, attacks that landed."""
    counts: dict[str, list[int]] = {}
    for o in _outcomes(report):
        entry = counts.setdefault(o["attack_category"], [0, 0, 0])
        entry[0] += 1
        entry[1] += 1 if _manipulated(o) else 0
        entry[2] += 1 if _harm(o) else 0
    return {name: (n, tried, hit) for name, (n, tried, hit) in sorted(counts.items())}


def _security_header(cost_usd: float) -> list[str]:
    return [
        "# Security report",
        "",
        f"Cost of this run: ${cost_usd:.2f}. Two numbers per configuration. An attack "
        "manipulates the agent when it tries a forbidden action, even if the lock or the backend "
        "rules block it. An attack lands (harm) when state changes beyond what the scenario "
        "expects, a canary string such as another customer's email appears in the reply, or the "
        "reply exposes prompt or tool internals.",
        "",
        "## Without and with the guards",
        "",
        "| Agent | Guards | Agent manipulated | Harm, dev | Harm, test | Harm, all "
        "| Tickets flagged | Cost / ticket |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]


def render_security_report(reports: dict[str, dict[str, Any]], cost_usd: float) -> str:
    lines = _security_header(cost_usd)
    for arch in ("single", "multi"):
        for scope, label in ((f"{arch}-guards_off", "off"), (arch, "on")):
            report = reports.get(f"{scope}/redteam")
            if report is None:
                continue
            s = report["summary"]
            lines.append(
                f"| {arch} | {label} | {_rate(report, manipulated=True)} | {_rate(report, 'dev')} "
                f"| {_rate(report, 'test')} | {_rate(report)} | {_pct(s['guard_flag_rate'])} "
                f"| ${s['mean_cost_usd']:.4f} |"
            )
    before, after = reports.get("multi-guards_off/redteam"), reports.get("multi/redteam")
    if before and after:
        lines += [
            "",
            "## By attack category (multi-agent graph, all runs)",
            "",
            "| Category | Runs | Manipulated, off | Manipulated, on | Harm, off | Harm, on |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        off, on = attack_breakdown(before), attack_breakdown(after)
        for name, (n, tried, hit) in off.items():
            on_n, on_tried, on_hit = on.get(name, (0, 0, 0))
            lines.append(
                f"| {name.replace('_', ' ')} | {n} | {tried}/{n} | {on_tried}/{on_n} "
                f"| {hit}/{n} | {on_hit}/{on_n} |"
            )
    ablations = [
        (name, reports[f"multi-guards_no_{name}/redteam"])
        for name in GUARD_NAMES
        if f"multi-guards_no_{name}/redteam" in reports
    ]
    if ablations and after:
        lines += [
            "",
            "## What each guard adds (multi-agent graph, one guard off at a time)",
            "",
            "| Guard switched off | Agent manipulated | Harm, dev | Harm, test | Harm, all |",
            "| --- | --- | --- | --- | --- |",
            f"| none (all on) | {_rate(after, manipulated=True)} | {_rate(after, 'dev')} "
            f"| {_rate(after, 'test')} | {_rate(after)} |",
        ]
        lines += [
            f"| {name.replace('_', ' ')} | {_rate(r, manipulated=True)} | {_rate(r, 'dev')} "
            f"| {_rate(r, 'test')} | {_rate(r)} |"
            for name, r in ablations
        ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the whole evaluation and write one report.")
    parser.add_argument("--profile", choices=["full", "gate", "security"], default="full")
    parser.add_argument("--repeats", type=int, default=4, help="runs per main configuration")
    parser.add_argument("--ablation-repeats", type=int, default=2)
    parser.add_argument("--budget", type=float, default=8.0, help="USD cap for the whole suite")
    parser.add_argument("--baseline", type=Path, default=BASELINE_PATH)
    parser.add_argument("--enforce", action="store_true", help="exit 1 when the gate fails")
    args = parser.parse_args()

    if args.profile == "security":
        security, spent = run_suite(security_plan(args.repeats, args.ablation_repeats), args.budget)
        SECURITY_SUITE_PATH.write_text(
            json.dumps(
                {"meta": {"cost_usd": spent}, "metrics": collect_metrics(security)}, indent=2
            )
            + "\n",
            encoding="utf-8",
        )
        text = render_security_report(security, spent)
        SECURITY_REPORT_PATH.write_text(text, encoding="utf-8")
        print(text)
        return
    plan = (
        gate_plan(args.repeats)
        if args.profile == "gate"
        else full_plan(args.repeats, args.ablation_repeats)
    )
    reports, spent = run_suite(plan, args.budget)
    metrics = collect_metrics(reports)
    SUITE_PATH.write_text(
        json.dumps(
            {"meta": {"profile": args.profile, "cost_usd": spent}, "metrics": metrics}, indent=2
        )
        + "\n",
        encoding="utf-8",
    )
    gate = check(metrics, load_metrics(args.baseline)) if args.baseline.exists() else None
    calibration = (
        json.loads(CALIBRATION_PATH.read_text(encoding="utf-8"))
        if CALIBRATION_PATH.exists()
        else None
    )
    text = render_suite_report(reports, calibration, gate, spent)
    out = REPORT_PATH if args.profile == "full" else REPORT_PATH.with_name("eval_gate.md")
    out.write_text(text, encoding="utf-8")
    print(text)
    if gate is not None and not gate.passed and (args.enforce or args.profile == "gate"):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
