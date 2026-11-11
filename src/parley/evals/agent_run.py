import logging
from collections.abc import Callable
from datetime import datetime

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from parley.agent.llm import LLMClient
from parley.agent.loop import run_ticket
from parley.agent.ticket import Ticket
from parley.backend.services import Backend
from parley.evals.schema import Scenario
from parley.evals.scoring import ScenarioOutcome, score
from parley.evals.state import take_snapshot
from parley.evals.world import WorldIndex, build_world, render_text
from parley.rag.retrieval import Retriever
from parley.seed.config import REFERENCE_NOW
from parley.tools.catalog import default_registry
from parley.tools.context import ToolContext

logger = logging.getLogger(__name__)

RetrieverFactory = Callable[[Session], Retriever | None]
LLMFactory = Callable[[Scenario, WorldIndex], LLMClient]


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
    result = await run_ticket(
        llm_factory(scenario, index),
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
) -> list[ScenarioOutcome]:
    """Run scenarios one by one, each in a transaction that is rolled back afterwards."""
    outcomes: list[ScenarioOutcome] = []
    spent = 0.0
    for scenario in scenarios:
        if spent >= total_budget_usd:
            logger.warning("total budget of %.2f USD reached, stopping early", total_budget_usd)
            break
        outcome = await _run_isolated(
            engine, scenario, llm_factory, retriever, model, max_steps, max_cost_usd
        )
        spent += outcome.cost_usd
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
        )
    except Exception as exc:
        logger.exception("scenario %s failed", scenario.id)
        return ScenarioOutcome.failed(scenario, f"{type(exc).__name__}: {exc}")
    finally:
        session.close()
        transaction.rollback()
        connection.close()
