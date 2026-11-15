import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from parley.agent.llm import LLMClient
from parley.agent.loop import run_ticket
from parley.agent.result import AgentResult
from parley.agent.ticket import Ticket
from parley.backend.services import Backend
from parley.evals.dialogue import run_dialogue
from parley.evals.schema import DialogueSpec, Scenario
from parley.evals.scoring import ScenarioOutcome, score
from parley.evals.state import take_snapshot
from parley.evals.tamper import TamperedRetriever
from parley.evals.world import WorldIndex, build_world, render_text
from parley.observability.llm import TracedLLM
from parley.observability.tracing import span
from parley.orchestration.graph import Switches
from parley.orchestration.runner import run_multi
from parley.rag.retrieval import Retriever
from parley.security.guards import GuardConfig
from parley.seed.config import REFERENCE_NOW
from parley.tools.catalog import default_registry
from parley.tools.context import ToolContext

logger = logging.getLogger(__name__)

MAX_CONSECUTIVE_ERRORS = 3

RetrieverFactory = Callable[[Session], Retriever | None]
LLMFactory = Callable[[Scenario, WorldIndex], LLMClient]


@dataclass(frozen=True)
class Architecture:
    """Single agent by default; the multi-agent graph needs a router model factory."""

    name: str = "single"
    router_llm_factory: LLMFactory | None = None
    critic_llm_factory: LLMFactory | None = None
    responder_llm_factory: LLMFactory | None = None
    max_revisions: int = 2
    switches: Switches = field(default_factory=Switches)
    guards: GuardConfig = field(default_factory=GuardConfig)


SINGLE = Architecture()


async def run_scenario(
    session: Session,
    scenario: Scenario,
    llm_factory: LLMFactory,
    retriever: RetrieverFactory,
    *,
    model: str,
    max_steps: int,
    max_cost_usd: float,
    now: datetime = REFERENCE_NOW,
    arch: Architecture = SINGLE,
    simulator: LLMClient | None = None,
) -> ScenarioOutcome:
    """Run one scenario inside a trace and return its scored outcome."""
    with span(
        "scenario",
        "scenario",
        scenario_id=scenario.id,
        arch=arch.name,
        category=scenario.category,
        guards=arch.guards.any_on,
    ) as handle:
        outcome = await _play(
            session,
            scenario,
            llm_factory,
            retriever,
            model=model,
            max_steps=max_steps,
            max_cost_usd=max_cost_usd,
            now=now,
            arch=arch,
            simulator=simulator,
        )
        handle.set(
            success=outcome.success,
            cost_usd=outcome.cost_usd,
            turns=outcome.turns,
            guard_events=outcome.guard_events,
        )
        return outcome.model_copy(update={"trace_id": handle.trace_id})


async def _play(
    session: Session,
    scenario: Scenario,
    llm_factory: LLMFactory,
    retriever: RetrieverFactory,
    *,
    model: str,
    max_steps: int,
    max_cost_usd: float,
    now: datetime,
    arch: Architecture,
    simulator: LLMClient | None,
) -> ScenarioOutcome:
    """Build the scenario world, let the agent handle its ticket, and score the final state."""
    index = build_world(session, scenario, now)
    backend = Backend(session, lambda: now)
    before = take_snapshot(session, index)
    ticket = Ticket(
        id=scenario.id,
        sender_email=scenario.ticket.sender_email,
        subject=render_text(scenario.ticket.subject, index),
        body=render_text(scenario.ticket.body, index),
    )
    customer = backend.find_customer_by_email(ticket.sender_email)
    llm = TracedLLM(llm_factory(scenario, index))
    if arch.name == "multi" and arch.router_llm_factory is None:
        raise ValueError("the multi architecture needs a router model")

    async def handle(turn_ticket: Ticket) -> AgentResult:
        with span("ticket", "ticket", ticket_id=turn_ticket.id):
            return await _handle(turn_ticket)

    async def _handle(turn_ticket: Ticket) -> AgentResult:
        ctx = ToolContext(
            backend,
            customer.id,
            turn_ticket.id,
            retriever=_retriever_for(scenario, retriever(session)),
            guards=arch.guards,
        )
        if arch.router_llm_factory is not None and arch.name == "multi":
            return await run_multi(
                TracedLLM(arch.router_llm_factory(scenario, index)),
                llm,
                ctx,
                turn_ticket,
                model=model,
                max_steps=max_steps,
                max_cost_usd=max_cost_usd,
                max_revisions=arch.max_revisions,
                switches=arch.switches,
                critic_llm=_role(arch.critic_llm_factory, scenario, index),
                responder_llm=_role(arch.responder_llm_factory, scenario, index),
            )
        return await run_ticket(
            llm,
            default_registry(),
            ctx,
            turn_ticket,
            model=model,
            max_steps=max_steps,
            max_cost_usd=max_cost_usd,
        )

    if scenario.dialogue is None:
        result = await handle(ticket)
        return score(scenario, index, before, take_snapshot(session, index), result)
    if simulator is None:
        raise ValueError(f"{scenario.id} is a dialogue and needs a user simulator")
    run = await run_dialogue(_render_dialogue(scenario.dialogue, index), ticket, simulator, handle)
    outcome = score(scenario, index, before, take_snapshot(session, index), run.result)
    return outcome.model_copy(
        update={
            "turns": int(run.result.extras["turns"]),
            "transcript": [f"[{t.role}] {t.text}" for t in run.turns],
            "simulator_cost_usd": run.simulator_usage.cost_usd,
        }
    )


def _role(factory: LLMFactory | None, scenario: Scenario, index: WorldIndex) -> LLMClient | None:
    return TracedLLM(factory(scenario, index)) if factory is not None else None


def _retriever_for(scenario: Scenario, found: Retriever | None) -> Retriever | None:
    if found is None or scenario.attack is None or not scenario.attack.tamper_policy:
        return found
    return TamperedRetriever(found, scenario.attack.tamper_policy)


def _render_dialogue(spec: DialogueSpec, index: WorldIndex) -> DialogueSpec:
    return spec.model_copy(
        update={
            "persona": render_text(spec.persona, index),
            "goal": render_text(spec.goal, index),
            "facts": [render_text(f, index) for f in spec.facts],
        }
    )


async def evaluate(
    engine: Engine,
    scenarios: list[Scenario],
    llm_factory: LLMFactory,
    retriever: RetrieverFactory,
    *,
    model: str,
    max_steps: int,
    max_cost_usd: float,
    total_budget_usd: float,
    on_outcome: Callable[[ScenarioOutcome], None] | None = None,
    arch: Architecture = SINGLE,
    already_spent_usd: float = 0.0,
    simulator: LLMClient | None = None,
) -> list[ScenarioOutcome]:
    """Run scenarios one by one, each in a transaction that is rolled back afterwards."""
    outcomes: list[ScenarioOutcome] = []
    spent = already_spent_usd
    consecutive_errors = 0
    for scenario in scenarios:
        if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
            logger.error("%d runs in a row crashed, aborting the evaluation", consecutive_errors)
            break
        if spent >= total_budget_usd:
            logger.warning("total budget of %.2f USD reached, stopping early", total_budget_usd)
            break
        outcome = await _run_isolated(
            engine,
            scenario,
            llm_factory,
            retriever,
            model,
            max_steps,
            max_cost_usd,
            arch,
            simulator,
        )
        spent += outcome.cost_usd + outcome.simulator_cost_usd
        consecutive_errors = consecutive_errors + 1 if outcome.error else 0
        outcomes.append(outcome)
        if on_outcome is not None:
            on_outcome(outcome)
    return outcomes


async def _run_isolated(
    engine: Engine,
    scenario: Scenario,
    llm_factory: LLMFactory,
    retriever: RetrieverFactory,
    model: str,
    max_steps: int,
    max_cost_usd: float,
    arch: Architecture,
    simulator: LLMClient | None,
) -> ScenarioOutcome:
    connection = engine.connect()
    transaction = connection.begin()
    session = Session(connection, join_transaction_mode="create_savepoint", expire_on_commit=False)
    try:
        return await run_scenario(
            session,
            scenario,
            llm_factory,
            retriever,
            model=model,
            max_steps=max_steps,
            max_cost_usd=max_cost_usd,
            arch=arch,
            simulator=simulator,
        )
    except Exception as exc:
        logger.exception("scenario %s failed", scenario.id)
        return ScenarioOutcome.failed(scenario, f"{type(exc).__name__}: {exc}")
    finally:
        session.close()
        transaction.rollback()
        connection.close()
