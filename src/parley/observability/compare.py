import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from parley.evals.report import percentile
from parley.observability.exporters import read_spans

Span = dict[str, Any]


@dataclass(frozen=True)
class RunStats:
    tickets: int
    success: float
    handover: float
    cost: float
    p50_s: float
    p95_s: float
    calls: float
    prompt_tokens: float
    cached_share: float
    attack_harm: float | None


def trace_file(report: Path) -> Path:
    return report.parent / "traces" / f"{report.stem}.jsonl"


def stats(report: dict[str, Any], spans: list[Span]) -> RunStats:
    outcomes = report["outcomes"]
    n = len(outcomes) or 1
    latencies = [o["latency_s"] for o in outcomes]
    llm = [s for s in spans if s["kind"] == "llm"]
    prompt = sum(s["attributes"].get("prompt_tokens", 0) for s in llm)
    cached = sum(s["attributes"].get("cached_tokens", 0) for s in llm)
    return RunStats(
        tickets=len(outcomes),
        success=sum(1 for o in outcomes if o["success"]) / n,
        handover=sum(1 for o in outcomes if o["handover_ok"]) / n,
        cost=sum(o["cost_usd"] for o in outcomes) / n,
        p50_s=percentile(latencies, 0.5),
        p95_s=percentile(latencies, 0.95),
        calls=len(llm) / n,
        prompt_tokens=prompt / n,
        cached_share=cached / prompt if prompt else 0.0,
        attack_harm=report["summary"].get("attack_success_rate"),
    )


def _change(before: float, after: float) -> str:
    return "n/a" if before == 0 else f"{(after - before) / before:+.0%}"


def render_table(rows: dict[str, tuple[RunStats, RunStats]]) -> str:
    lines = [
        "| Set | Metric | Before | After | Change |",
        "| --- | --- | --- | --- | --- |",
    ]
    for label, (b, a) in rows.items():
        entries = [
            (
                "Task success",
                f"{b.success:.1%}",
                f"{a.success:.1%}",
                f"{a.success - b.success:+.1%}",
            ),
            (
                "Handover correct",
                f"{b.handover:.1%}",
                f"{a.handover:.1%}",
                f"{a.handover - b.handover:+.1%}",
            ),
            ("Cost per ticket", f"${b.cost:.4f}", f"${a.cost:.4f}", _change(b.cost, a.cost)),
            ("Latency p50", f"{b.p50_s:.1f}s", f"{a.p50_s:.1f}s", _change(b.p50_s, a.p50_s)),
            ("Latency p95", f"{b.p95_s:.1f}s", f"{a.p95_s:.1f}s", _change(b.p95_s, a.p95_s)),
            (
                "Model calls per ticket",
                f"{b.calls:.2f}",
                f"{a.calls:.2f}",
                _change(b.calls, a.calls),
            ),
            (
                "Prompt tokens per ticket",
                f"{b.prompt_tokens:,.0f}",
                f"{a.prompt_tokens:,.0f}",
                _change(b.prompt_tokens, a.prompt_tokens),
            ),
            (
                "Share of prompt tokens cached",
                f"{b.cached_share:.0%}",
                f"{a.cached_share:.0%}",
                f"{a.cached_share - b.cached_share:+.0%}",
            ),
        ]
        if a.attack_harm is not None and b.attack_harm is not None:
            entries.append(
                ("Attacks that landed", f"{b.attack_harm:.1%}", f"{a.attack_harm:.1%}", "")
            )
        lines += [
            f"| {label} ({a.tickets} tickets) | {m} | {x} | {y} | {z} |" for m, x, y, z in entries
        ]
    return "\n".join(lines) + "\n"


def load(report: Path) -> RunStats:
    data = json.loads(report.read_text(encoding="utf-8"))
    return stats(data, read_spans(trace_file(report)))


def main() -> None:
    parser = argparse.ArgumentParser(description="Before and after table from eval reports.")
    parser.add_argument("pairs", nargs="+", help="label=before.json,after.json")
    args = parser.parse_args()
    rows: dict[str, tuple[RunStats, RunStats]] = {}
    for pair in args.pairs:
        label, _, files = pair.partition("=")
        before, _, after = files.partition(",")
        rows[label] = (load(Path(before)), load(Path(after)))
    print(render_table(rows))


if __name__ == "__main__":
    main()
