import math
from collections import defaultdict
from collections.abc import Callable

from pydantic import BaseModel

from parley.evals.scoring import ScenarioOutcome
from parley.orchestration.router import CATEGORY_SPECIALIST


class Summary(BaseModel):
    n: int
    success_rate: float
    state_ok_rate: float
    reply_rate: float
    handover_accuracy: float
    forbidden_attempt_rate: float
    unbacked_claim_rate: float
    router_accuracy: float | None
    mean_revisions: float
    error_rate: float
    mean_policy_recall: float | None
    tool_error_rate: float
    mean_steps: float
    mean_tool_calls: float
    mean_cost_usd: float
    total_cost_usd: float
    latency_p50_s: float
    latency_p95_s: float


def percentile(values: list[float], q: float) -> float:
    """Nearest-rank percentile; 0.0 for an empty list."""
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(q * len(ordered)))
    return ordered[rank - 1]


def _rate(outcomes: list[ScenarioOutcome], test: Callable[[ScenarioOutcome], bool]) -> float:
    return sum(1 for o in outcomes if test(o)) / len(outcomes) if outcomes else 0.0


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def summarize(outcomes: list[ScenarioOutcome]) -> Summary:
    recalls = [o.policy_recall for o in outcomes if o.policy_recall is not None]
    routed = [o for o in outcomes if o.specialist is not None]
    calls = sum(len(o.tool_calls) for o in outcomes)
    latencies = [o.latency_s for o in outcomes]
    return Summary(
        n=len(outcomes),
        success_rate=_rate(outcomes, lambda o: o.success),
        state_ok_rate=_rate(outcomes, lambda o: o.state_ok),
        reply_rate=_rate(outcomes, lambda o: o.replied),
        handover_accuracy=_rate(outcomes, lambda o: o.handover_ok),
        forbidden_attempt_rate=_rate(outcomes, lambda o: bool(o.forbidden_attempts)),
        unbacked_claim_rate=_rate(outcomes, lambda o: bool(o.unbacked_claims)),
        router_accuracy=(
            _rate(routed, lambda o: o.specialist == CATEGORY_SPECIALIST[o.category].value)
            if routed
            else None
        ),
        mean_revisions=_mean([float(o.revisions) for o in outcomes]),
        error_rate=_rate(outcomes, lambda o: o.error is not None),
        mean_policy_recall=_mean(recalls) if recalls else None,
        tool_error_rate=sum(o.tool_errors for o in outcomes) / calls if calls else 0.0,
        mean_steps=_mean([float(o.steps) for o in outcomes]),
        mean_tool_calls=calls / len(outcomes) if outcomes else 0.0,
        mean_cost_usd=_mean([o.cost_usd for o in outcomes]),
        total_cost_usd=sum(o.cost_usd for o in outcomes),
        latency_p50_s=percentile(latencies, 0.5),
        latency_p95_s=percentile(latencies, 0.95),
    )


def group_by(
    outcomes: list[ScenarioOutcome], key: Callable[[ScenarioOutcome], str]
) -> dict[str, Summary]:
    groups: dict[str, list[ScenarioOutcome]] = defaultdict(list)
    for outcome in outcomes:
        groups[key(outcome)].append(outcome)
    return {name: summarize(items) for name, items in sorted(groups.items())}


def render_markdown(outcomes: list[ScenarioOutcome], model: str) -> str:
    total = summarize(outcomes)
    lines = [
        f"Model: `{model}`. Scenarios: {total.n}.",
        "",
        "| Metric | Value |",
        "| --- | --- |",
        f"| Task success (state matches and a reply was written) | {total.success_rate:.1%} |",
        f"| State matches expected diff | {total.state_ok_rate:.1%} |",
        f"| Forbidden action attempted | {total.forbidden_attempt_rate:.1%} |",
        f"| Reply claims an action that did not happen | {total.unbacked_claim_rate:.1%} |",
        f"| Handover decision correct | {total.handover_accuracy:.1%} |",
        f"| Tool calls that returned an error | {total.tool_error_rate:.1%} |",
        *(
            [f"| Router picked the expected specialist | {total.router_accuracy:.1%} |"]
            if total.router_accuracy is not None
            else []
        ),
        f"| Mean cost per ticket | ${total.mean_cost_usd:.4f} |",
        f"| Latency p50 / p95 | {total.latency_p50_s:.1f}s / {total.latency_p95_s:.1f}s |",
    ]
    for title, key in (
        ("Category", lambda o: o.category),
        ("Difficulty", lambda o: o.difficulty),
    ):
        lines += [
            "",
            f"| {title} | n | success | handover | cost |",
            "| --- | --- | --- | --- | --- |",
        ]
        for name, s in group_by(outcomes, key).items():
            lines.append(
                f"| {name} | {s.n} | {s.success_rate:.0%} | {s.handover_accuracy:.0%} "
                f"| ${s.mean_cost_usd:.4f} |"
            )
    failed = [o.scenario_id for o in outcomes if not o.success]
    lines += ["", "Failed: " + (", ".join(failed) if failed else "none")]
    return "\n".join(lines) + "\n"


class RepeatSummary(BaseModel):
    runs: int
    success_mean: float
    success_min: float
    success_max: float
    pass_all: float
    pass_any: float
    unstable: list[str]


def summarize_repeats(runs: list[list[ScenarioOutcome]]) -> RepeatSummary:
    """Variance across repeated runs: pass^k is the share of scenarios solved in every run."""
    rates = [summarize(run).success_rate for run in runs]
    results: dict[str, list[bool]] = defaultdict(list)
    for run in runs:
        for outcome in run:
            results[outcome.scenario_id].append(outcome.success)
    total = len(results)
    return RepeatSummary(
        runs=len(runs),
        success_mean=_mean(rates),
        success_min=min(rates) if rates else 0.0,
        success_max=max(rates) if rates else 0.0,
        pass_all=sum(1 for r in results.values() if all(r)) / total if total else 0.0,
        pass_any=sum(1 for r in results.values() if any(r)) / total if total else 0.0,
        unstable=sorted(sid for sid, r in results.items() if any(r) and not all(r)),
    )
