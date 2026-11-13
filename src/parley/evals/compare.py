import json
import sys
from pathlib import Path
from typing import Any


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def _success(report: dict[str, Any]) -> str:
    repeats = report.get("repeats")
    if repeats:
        return (
            f"{repeats['success_mean']:.1%} "
            f"({repeats['success_min']:.1%} to {repeats['success_max']:.1%})"
        )
    return _pct(report["summary"]["success_rate"])


def _pass_all(report: dict[str, Any]) -> str:
    repeats = report.get("repeats")
    return _pct(repeats["pass_all"]) if repeats else "n/a"


def render_comparison(single: dict[str, Any], multi: dict[str, Any]) -> str:
    """Side-by-side table of two evaluation reports built by the agent eval command."""
    a, b = single["summary"], multi["summary"]
    runs = multi.get("repeats", {}).get("runs") or multi["meta"].get("repeats", 1)
    rows = [
        ("Task success per run (mean, range)", _success(single), _success(multi)),
        (f"Solved in every one of {runs} runs (pass^{runs})", _pass_all(single), _pass_all(multi)),
        (
            "Forbidden action attempted",
            _pct(a["forbidden_attempt_rate"]),
            _pct(b["forbidden_attempt_rate"]),
        ),
        (
            "Reply claims an action that did not happen",
            _pct(a["unbacked_claim_rate"]),
            _pct(b["unbacked_claim_rate"]),
        ),
        ("Handover decision correct", _pct(a["handover_accuracy"]), _pct(b["handover_accuracy"])),
        (
            "Policy violation (forbidden action or stale citation)",
            _pct(a.get("policy_violation_rate")),
            _pct(b.get("policy_violation_rate")),
        ),
        (
            "Refunds and cancellations that were right (precision)",
            _pct(a.get("tool_precision")),
            _pct(b.get("tool_precision")),
        ),
        (
            "Expected refunds and cancellations that were done (recall)",
            _pct(a.get("tool_recall")),
            _pct(b.get("tool_recall")),
        ),
        ("Tool calls with an error", _pct(a["tool_error_rate"]), _pct(b["tool_error_rate"])),
        ("Router picked the expected specialist", "n/a", _pct(b["router_accuracy"])),
        (
            "Mean cost per ticket",
            f"${a['mean_cost_usd']:.4f}",
            f"${b['mean_cost_usd']:.4f}",
        ),
        (
            "Latency p50 / p95",
            f"{a['latency_p50_s']:.1f}s / {a['latency_p95_s']:.1f}s",
            f"{b['latency_p50_s']:.1f}s / {b['latency_p95_s']:.1f}s",
        ),
    ]
    lines = ["| Metric | Single agent | Multi-agent |", "| --- | --- | --- |"]
    lines += [f"| {name} | {left} | {right} |" for name, left, right in rows]
    return "\n".join(lines) + "\n"


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("usage: python -m parley.evals.compare <single.json> <multi.json>")
    single, multi = (json.loads(Path(p).read_text(encoding="utf-8")) for p in sys.argv[1:])
    print(render_comparison(single, multi))


if __name__ == "__main__":
    main()
