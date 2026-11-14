import math
from collections import defaultdict
from collections.abc import Callable

from pydantic import BaseModel

from parley.evals.scoring import ScenarioOutcome
from parley.orchestration.router import ACCEPTED_SPECIALISTS


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
    policy_violation_rate: float | None = None
    judge_pass_rates: dict[str, float] | None = None
    attack_success_rate: float | None = None
    guard_flag_rate: float = 0.0
    tool_precision: float | None = None
    tool_recall: float | None = None
    critic_unparsed_rate: float = 0.0
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


def _judge_rates(outcomes: list[ScenarioOutcome]) -> dict[str, float] | None:
    graded = [o.judge for o in outcomes if o.judge]
    if not graded:
        return None
    return {name: sum(1 for g in graded if g[name]) / len(graded) for name in graded[0]}


def _attack_rate(outcomes: list[ScenarioOutcome]) -> float | None:
    attacks = [o for o in outcomes if o.attack_success is not None]
    if not attacks:
        return None
    return sum(1 for o in attacks if o.attack_success) / len(attacks)


def _ratio(part: int, whole: int) -> float | None:
    return part / whole if whole else None


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def summarize(outcomes: list[ScenarioOutcome]) -> Summary:
    recalls = [o.policy_recall for o in outcomes if o.policy_recall is not None]
    routed = [o for o in outcomes if o.specialist is not None]
    calls = sum(len(o.tool_calls) for o in outcomes)
    executed = sum(o.writes_executed for o in outcomes)
    expected = sum(o.writes_expected for o in outcomes)
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
            _rate(
                routed,
                lambda o: o.specialist in {s.value for s in ACCEPTED_SPECIALISTS[o.category]},
            )
            if routed
            else None
        ),
        mean_revisions=_mean([float(o.revisions) for o in outcomes]),
        policy_violation_rate=_rate(outcomes, lambda o: not o.policy_compliant),
        judge_pass_rates=_judge_rates(outcomes),
        attack_success_rate=_attack_rate(outcomes),
        guard_flag_rate=_rate(outcomes, lambda o: o.guard_flagged),
        tool_precision=_ratio(sum(o.writes_correct for o in outcomes), executed),
        tool_recall=_ratio(sum(o.writes_found for o in outcomes), expected),
        critic_unparsed_rate=_rate(outcomes, lambda o: o.critic_source == "unparsed"),
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
        *(
            [f"| Attack success rate | {total.attack_success_rate:.1%} |"]
            if total.attack_success_rate is not None
            else []
        ),
        f"| Tickets flagged by the injection scan | {total.guard_flag_rate:.1%} |",
        f"| Policy violation (forbidden action or stale citation) | "
        f"{_pct(total.policy_violation_rate)} |",
        f"| Reply claims an action that did not happen | {total.unbacked_claim_rate:.1%} |",
        f"| Handover decision correct | {total.handover_accuracy:.1%} |",
        f"| Tool calls that returned an error | {total.tool_error_rate:.1%} |",
        f"| Refunds and cancellations that were right (precision) | {_pct(total.tool_precision)} |",
        f"| Expected refunds and cancellations that were done (recall) | "
        f"{_pct(total.tool_recall)} |",
        *(
            [
                f"| Router picked the expected specialist | {total.router_accuracy:.1%} |",
                f"| Critic answer unreadable, plan approved unreviewed | "
                f"{total.critic_unparsed_rate:.1%} |",
            ]
            if total.router_accuracy is not None
            else []
        ),
        *(
            f"| Judge: {name.replace('_', ' ')} | {rate:.1%} |"
            for name, rate in (total.judge_pass_rates or {}).items()
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


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


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


def render_repeats(r: RepeatSummary) -> str:
    unstable = ", ".join(r.unstable) if r.unstable else "none"
    return (
        f"\nRepeats: {r.runs} runs. Success {r.success_min:.1%} to {r.success_max:.1%} "
        f"(mean {r.success_mean:.1%}). Solved in every run (pass^{r.runs}): {r.pass_all:.1%}. "
        f"Solved in at least one run: {r.pass_any:.1%}. Unstable scenarios: {unstable}.\n"
    )
