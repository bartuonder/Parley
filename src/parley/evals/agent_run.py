import logging
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from parley.agent.llm import LLMClient
from parley.agent.loop import run_ticket
from parley.agent.result import AgentResult
from parley.agent.ticket import Ticket
from parley.backend.services import Backend
from parley.evals.schema import Scenario
from parley.evals.scoring import ScenarioOutcome, score
from parley.evals.state import take_snapshot
from parley.evals.world import WorldIndex, build_world, render_text
from parley.orchestration.runner import run_multi
from parley.rag.retrieval import Retriever
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
    max_revisions: int = 2


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
    ctx = ToolContext(backend, customer.id, ticket.id, retriever=retriever(session))
    llm = llm_factory(scenario, index)
    result: AgentResult
    if arch.name == "multi":
        if arch.router_llm_factory is None:
            raise ValueError("the multi architecture needs a router model")
        result = await run_multi(
            arch.router_llm_factory(scenario, index),
            llm,
            ctx,
            ticket,
            model=model,
            max_steps=max_steps,
            max_cost_usd=max_cost_usd,
            max_revisions=arch.max_revisions,
        )
    else:
        result = await run_ticket(
            llm,
            default_registry(),
            ctx,
            ticket,
            model=model,
            max_steps=max_steps,
            max_cost_usd=max_cost_usd,
        )
    return score(scenario, index, before, take_snapshot(session, index), result)


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
            engine, scenario, llm_factory, retriever, model, max_steps, max_cost_usd, arch
        )
        spent += outcome.cost_usd
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
        )
    except Exception as exc:
        logger.exception("scenario %s failed", scenario.id)
        return ScenarioOutcome.failed(scenario, f"{type(exc).__name__}: {exc}")
    finally:
        session.close()
        transaction.rollback()
        connection.close()
