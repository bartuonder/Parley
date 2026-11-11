import argparse
import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from parley.agent.llm import LiteLLMClient
from parley.db.session import session_scope
from parley.evals.agent_run import evaluate
from parley.evals.database import recreate_eval_database
from parley.evals.loader import load_scenarios
from parley.evals.report import group_by, render_markdown, summarize
from parley.evals.schema import Scenario
from parley.evals.scoring import ScenarioOutcome
from parley.rag.service import build_default_index, default_retriever
from parley.settings import PROJECT_ROOT, get_settings

DEFAULT_OUT = PROJECT_ROOT / "reports" / "agent_baseline.json"
DEFAULT_TOTAL_BUDGET_USD = 3.0


def select_scenarios(
    scenarios: list[Scenario], ids: list[str], category: str | None, limit: int | None
) -> list[Scenario]:
    chosen = [
        s
        for s in scenarios
        if (not ids or s.id in ids) and (not category or s.category == category)
    ]
    unknown = sorted(set(ids) - {s.id for s in scenarios})
    if unknown:
        raise SystemExit(f"unknown scenario ids: {', '.join(unknown)}")
    return chosen[:limit] if limit else chosen


def build_report(
    outcomes: list[ScenarioOutcome], model: str, limits: dict[str, Any]
) -> dict[str, Any]:
    return {
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


def is_complete(outcomes: list[ScenarioOutcome], expected: int) -> bool:
    """A report is only worth keeping if every selected scenario ran without crashing."""
    return len(outcomes) == expected and all(o.error is None for o in outcomes)


def print_progress(outcome: ScenarioOutcome) -> None:
    flag = "ok  " if outcome.success else "FAIL"
    extra = f" error={outcome.error}" if outcome.error else ""
    print(
        f"{outcome.scenario_id:8} {flag} ${outcome.cost_usd:.4f} {outcome.latency_s:5.1f}s "
        f"calls={len(outcome.tool_calls)}{extra}",
        flush=True,
    )


async def run(args: argparse.Namespace, scenarios: list[Scenario]) -> list[ScenarioOutcome]:
    settings = get_settings()
    if settings.llm_api_key is None:
        raise SystemExit("PARLEY_LLM_API_KEY is not set")
    model = args.model or settings.agent_model
    engine = recreate_eval_database()
    try:
        with session_scope(engine) as session:
            build_default_index(session)
        client = LiteLLMClient(model=model)
        return await evaluate(
            engine,
            scenarios,
            lambda scenario, index: client,
            lambda session: default_retriever(session),
            model=model,
            max_steps=settings.agent_max_steps,
            max_cost_usd=settings.agent_max_cost_usd,
            total_budget_usd=args.budget,
            on_outcome=print_progress,
        )
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the agent on the eval scenarios.")
    parser.add_argument("--ids", nargs="*", default=[], help="scenario ids to run")
    parser.add_argument("--category", help="only this ticket category")
    parser.add_argument("--limit", type=int, help="run at most this many scenarios")
    parser.add_argument("--model", help="override PARLEY_AGENT_MODEL")
    parser.add_argument("--budget", type=float, default=DEFAULT_TOTAL_BUDGET_USD, help="USD cap")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    scenarios = select_scenarios(load_scenarios(), args.ids, args.category, args.limit)
    outcomes = asyncio.run(run(args, scenarios))
    settings = get_settings()
    model = args.model or settings.agent_model
    print(render_markdown(outcomes, model))
    if not is_complete(outcomes, len(scenarios)):
        raise SystemExit("run incomplete or had crashed scenarios; report not written")

    limits = {
        "max_steps": settings.agent_max_steps,
        "max_cost_usd": settings.agent_max_cost_usd,
        "total_budget_usd": args.budget,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    report = build_report(outcomes, model, limits)
    args.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    args.out.with_suffix(".md").write_text(render_markdown(outcomes, model), encoding="utf-8")


if __name__ == "__main__":
    main()
