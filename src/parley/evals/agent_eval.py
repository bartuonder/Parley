import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from parley.agent.llm import LiteLLMClient
from parley.db.session import session_scope
from parley.evals.agent_run import Architecture, evaluate
from parley.evals.database import recreate_eval_database
from parley.evals.judge import judge_outcomes
from parley.evals.loader import SCENARIO_SETS, load_set
from parley.evals.report import (
    RepeatSummary,
    group_by,
    render_markdown,
    render_repeats,
    summarize,
    summarize_repeats,
)
from parley.evals.schema import Scenario
from parley.evals.scoring import ScenarioOutcome
from parley.observability.exporters import JsonlExporter
from parley.observability.tracing import telemetry
from parley.orchestration.classifier import ClassifierRouter, RouterModel
from parley.orchestration.graph import Switches
from parley.rag.embedders import get_embedder
from parley.rag.service import DEFAULT_EMBEDDING, build_default_index, default_retriever
from parley.security.guards import parse_guards
from parley.settings import PROJECT_ROOT, get_settings

DEFAULT_TOTAL_BUDGET_USD = 3.0


ABLATIONS: dict[str, Switches] = {
    "critic": Switches(critic=False),
    "rewrite": Switches(rewrite=False),
    "router": Switches(route=False),
}


def default_out(
    arch: str, scenario_set: str = "core", ablation: str | None = None, guards: str = "on"
) -> Path:
    name = f"agent_{arch}" + (f"_no_{ablation}" if ablation else "")
    name += "" if guards == "on" else f"_guards_{guards}"
    suffix = "" if scenario_set == "core" else f"_{scenario_set}"
    return PROJECT_ROOT / "reports" / f"{name}{suffix}.json"


def build_classifier(args: argparse.Namespace, router: LiteLLMClient) -> ClassifierRouter | None:
    if args.router == "llm":
        return None
    return ClassifierRouter(
        RouterModel.load(),
        get_embedder(DEFAULT_EMBEDDING),
        threshold=0.0 if args.router == "classifier" else args.router_threshold,
        fallback=router if args.router == "hybrid" else None,
    )


def trace_path(report_path: Path) -> Path:
    return report_path.parent / "traces" / f"{report_path.stem}.jsonl"


def select_scenarios(
    scenarios: list[Scenario],
    ids: list[str],
    category: str | None,
    limit: int | None,
    split: str | None = None,
) -> list[Scenario]:
    chosen = [
        s
        for s in scenarios
        if (not ids or s.id in ids)
        and (not category or s.category == category)
        and (not split or (s.attack is not None and s.attack.split == split))
    ]
    unknown = sorted(set(ids) - {s.id for s in scenarios})
    if unknown:
        raise SystemExit(f"unknown scenario ids: {', '.join(unknown)}")
    return chosen[:limit] if limit else chosen


def needs_simulator(scenarios: list[Scenario]) -> bool:
    return any(s.dialogue is not None for s in scenarios)


def build_report(
    outcomes: list[ScenarioOutcome],
    model: str,
    limits: dict[str, Any],
    runs: list[list[ScenarioOutcome]] | None = None,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "meta": {"model": model, "run_at": datetime.now(UTC).isoformat(), **limits},
        "summary": summarize(outcomes).model_dump(),
        "by_category": {
            k: v.model_dump() for k, v in group_by(outcomes, lambda o: o.category).items()
        },
        "by_difficulty": {
            k: v.model_dump() for k, v in group_by(outcomes, lambda o: o.difficulty).items()
        },
        "outcomes": [o.model_dump(mode="json") for o in outcomes],
    }
    if runs is not None and len(runs) > 1:
        report["repeats"] = summarize_repeats(runs).model_dump()
        report["per_run"] = [summarize(run).model_dump() for run in runs]
    return report


def is_complete(outcomes: list[ScenarioOutcome], expected: int) -> bool:
    """A report is only worth keeping if every selected scenario ran without crashing."""
    return len(outcomes) == expected and all(o.error is None for o in outcomes)


def print_progress(outcome: ScenarioOutcome) -> None:
    flag = "ok  " if outcome.success else "FAIL"
    extra = f" error={outcome.error}" if outcome.error else ""
    route = f" via={outcome.specialist}" if outcome.specialist else ""
    print(
        f"{outcome.scenario_id:8} {flag} ${outcome.cost_usd:.4f} {outcome.latency_s:5.1f}s "
        f"calls={len(outcome.tool_calls)}{route}{extra}",
        flush=True,
    )


async def run(args: argparse.Namespace, scenarios: list[Scenario]) -> list[list[ScenarioOutcome]]:
    settings = get_settings()
    if settings.llm_api_key is None:
        raise SystemExit("PARLEY_LLM_API_KEY is not set")
    model = args.model or settings.agent_model
    engine = recreate_eval_database()
    guards = parse_guards(args.guards)
    arch = Architecture(guards=guards, compact_tools=args.compact, prefetch_overview=args.prefetch)
    if args.arch == "multi":
        router = LiteLLMClient(model=args.router_model or settings.router_model)
        critic = LiteLLMClient(model=args.critic_model) if args.critic_model else None
        responder = LiteLLMClient(model=args.responder_model) if args.responder_model else None
        arch = Architecture(
            name="multi",
            classifier=build_classifier(args, router),
            router_llm_factory=lambda scenario, index: router,
            critic_llm_factory=(lambda scenario, index: critic) if critic else None,
            responder_llm_factory=(lambda scenario, index: responder) if responder else None,
            max_revisions=settings.agent_max_revisions,
            switches=ABLATIONS.get(args.ablate or "", Switches()),
            guards=guards,
            compact_tools=args.compact,
            prefetch_overview=args.prefetch,
        )
    try:
        with session_scope(engine) as session:
            build_default_index(session)
        client = LiteLLMClient(model=model)
        simulator = (
            LiteLLMClient(model=settings.simulator_model) if needs_simulator(scenarios) else None
        )
        judge = LiteLLMClient(model=settings.judge_model) if args.judge else None
        runs: list[list[ScenarioOutcome]] = []
        spent = 0.0
        for number in range(1, args.repeats + 1):
            print(f"--- {args.arch} run {number} of {args.repeats}", flush=True)
            outcomes = await evaluate(
                engine,
                scenarios,
                lambda scenario, index: client,
                lambda session: default_retriever(session),
                model=model,
                max_steps=settings.agent_max_steps,
                max_cost_usd=settings.agent_max_cost_usd,
                total_budget_usd=args.budget,
                on_outcome=print_progress,
                arch=arch,
                already_spent_usd=spent,
                simulator=simulator,
            )
            if judge is not None and outcomes:
                outcomes = await judge_outcomes(judge, outcomes, scenarios)
            spent += sum(o.cost_usd + o.simulator_cost_usd + o.judge_cost_usd for o in outcomes)
            runs.append(outcomes)
            if not is_complete(outcomes, len(scenarios)):
                break
        return runs
    finally:
        engine.dispose()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the agent on the eval scenarios.")
    parser.add_argument("--arch", choices=["single", "multi"], default="single")
    parser.add_argument("--set", dest="scenario_set", choices=sorted(SCENARIO_SETS), default="core")
    parser.add_argument("--repeats", type=int, default=1, help="how many times to run the set")
    parser.add_argument("--ids", nargs="*", default=[], help="scenario ids to run")
    parser.add_argument("--category", help="only this ticket category")
    parser.add_argument("--limit", type=int, help="run at most this many scenarios")
    parser.add_argument("--split", choices=["dev", "test"], help="only attacks of this split")
    parser.add_argument(
        "--ablate", choices=sorted(ABLATIONS), help="turn one part of the multi-agent graph off"
    )
    parser.add_argument(
        "--guards", default="on", help="on, off, or no_<guard> to switch one defense off"
    )
    parser.add_argument(
        "--router",
        choices=["llm", "classifier", "hybrid"],
        default=None,
        help="how tickets route; the default is the model router",
    )
    parser.add_argument("--compact", action="store_true", help="leave empty fields out of tools")
    parser.add_argument(
        "--prefetch",
        action=argparse.BooleanOptionalAction,
        default=False,
        help="read the customer overview before the first turn (cheaper, less thorough)",
    )
    parser.add_argument("--router-threshold", type=float, default=0.5)
    parser.add_argument("--router-model", help="model of the router, default PARLEY_ROUTER_MODEL")
    parser.add_argument("--critic-model", help="model of the critic, default the agent model")
    parser.add_argument("--responder-model", help="model of the responder, default the agent model")
    parser.add_argument("--no-trace", action="store_true", help="do not write the span file")
    parser.add_argument("--judge", action="store_true", help="grade every reply with the LLM judge")
    parser.add_argument("--model", help="override PARLEY_AGENT_MODEL")
    parser.add_argument("--budget", type=float, default=DEFAULT_TOTAL_BUDGET_USD, help="USD cap")
    parser.add_argument("--out", type=Path, help="report path, default reports/agent_<arch>.json")
    args = parser.parse_args(argv)
    if args.ablate and args.arch != "multi":
        parser.error("--ablate applies to the multi-agent graph only")
    try:
        parse_guards(args.guards)
    except ValueError as exc:
        parser.error(str(exc))
    args.router = args.router or "llm"
    return args


def execute(args: argparse.Namespace) -> dict[str, Any]:
    """Run one configuration, write its report files, and return the report."""
    scenarios = select_scenarios(
        load_set(args.scenario_set), args.ids, args.category, args.limit, args.split
    )
    if not scenarios:
        raise SystemExit(f"no scenarios selected from the {args.scenario_set} set")
    out = args.out or default_out(args.arch, args.scenario_set, args.ablate, args.guards)
    traces = trace_path(out)
    if not args.no_trace:
        traces.parent.mkdir(parents=True, exist_ok=True)
        traces.write_text("", encoding="utf-8")
        telemetry.configure([JsonlExporter(traces)])
    try:
        runs = asyncio.run(run(args, scenarios))
    finally:
        telemetry.shutdown()
    settings = get_settings()
    model = args.model or settings.agent_model
    flat = [o for run_outcomes in runs for o in run_outcomes]
    repeats: RepeatSummary | None = summarize_repeats(runs) if len(runs) > 1 else None
    print(render_markdown(flat, model))
    if repeats is not None:
        print(render_repeats(repeats))
    complete = len(runs) == args.repeats and all(is_complete(r, len(scenarios)) for r in runs)
    if not complete:
        raise SystemExit("run incomplete or had crashed scenarios; report not written")

    limits = {
        "arch": args.arch,
        "scenario_set": args.scenario_set,
        "repeats": args.repeats,
        "router_model": (args.router_model or settings.router_model)
        if args.arch == "multi"
        else None,
        "router": args.router,
        "compact_tools": args.compact,
        "prefetch": args.prefetch,
        "critic_model": args.critic_model,
        "responder_model": args.responder_model,
        "simulator_model": settings.simulator_model if needs_simulator(scenarios) else None,
        "judge_model": settings.judge_model if args.judge else None,
        "ablation": args.ablate,
        "guards": args.guards,
        "max_steps": settings.agent_max_steps,
        "max_cost_usd": settings.agent_max_cost_usd,
        "max_revisions": settings.agent_max_revisions if args.arch == "multi" else None,
        "total_budget_usd": args.budget,
        "traces": None if args.no_trace else traces.name,
    }
    report = build_report(flat, model, limits, runs)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n", "utf-8")
    text = render_markdown(flat, model) + (render_repeats(repeats) if repeats else "")
    out.with_suffix(".md").write_text(text, encoding="utf-8")
    return report


def main() -> None:
    execute(parse_args())


if __name__ == "__main__":
    main()
