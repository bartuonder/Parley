import asyncio
import json
from typing import Any

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from parley.agent.llm import LLMClient, LLMResponse, Message
from parley.evals.agent_run import LLMFactory, evaluate, run_scenario
from parley.evals.loader import load_scenarios
from parley.evals.schema import Scenario
from parley.evals.scoring import ScenarioOutcome
from parley.evals.world import WorldIndex
from tests.fakes import ScriptedLLM, call_turn, reference_llm, reply_turn

SCENARIOS = load_scenarios()
MODEL = "scripted"
MAX_STEPS = 8
MAX_COST = 1.0


def no_retriever(_: Session) -> None:
    return None


def play(session: Session, scenario: Scenario, llm_for: LLMFactory) -> ScenarioOutcome:
    return asyncio.run(
        run_scenario(
            session,
            scenario,
            llm_for,
            no_retriever,
            model=MODEL,
            max_steps=MAX_STEPS,
            max_cost_usd=MAX_COST,
        )
    )


def run_all(
    engine: Engine, scenarios: list[Scenario], llm_for: LLMFactory, budget: float
) -> list[ScenarioOutcome]:
    return asyncio.run(
        evaluate(
            engine,
            scenarios,
            llm_for,
            no_retriever,
            model=MODEL,
            max_steps=MAX_STEPS,
            max_cost_usd=MAX_COST,
            total_budget_usd=budget,
        )
    )


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s.id for s in SCENARIOS])
def test_reference_agent_scores_perfectly_through_the_whole_stack(
    scenario: Scenario, session: Session
) -> None:
    outcome = play(session, scenario, reference_llm)
    assert outcome.state_ok and outcome.success
    assert outcome.forbidden_attempts == []
    assert outcome.handover_ok
    assert outcome.error is None


def test_attempting_a_forbidden_refund_is_flagged_even_though_the_backend_blocks_it(
    session: Session,
) -> None:
    scenario = next(s for s in SCENARIOS if s.id == "ADV-001")
    forbidden = scenario.forbidden_actions[0]

    def greedy(s: Scenario, index: WorldIndex) -> LLMClient:
        args = {
            "target": "order",
            "target_id": index.orders[forbidden.alias],
            "amount_cents": forbidden.amount_cents,
            "reason": "override",
        }
        return ScriptedLLM([call_turn("issue_refund", json.dumps(args)), reply_turn("Refunded.")])

    outcome = play(session, scenario, greedy)
    assert outcome.state_ok
    assert outcome.forbidden_attempts == ["issue_refund order o1"]
    assert outcome.tool_errors == 1


def test_a_crashing_model_becomes_a_failed_outcome_and_the_run_continues(engine: Engine) -> None:
    class Broken:
        async def complete(
            self, messages: list[Message], tools: list[dict[str, Any]]
        ) -> LLMResponse:
            raise RuntimeError("api down")

    scenarios = SCENARIOS[:2]
    outcomes = run_all(engine, scenarios, lambda s, i: Broken(), budget=5.0)
    assert [o.scenario_id for o in outcomes] == [s.id for s in scenarios]
    assert all(not o.success and o.error and "api down" in o.error for o in outcomes)


def test_total_budget_stops_the_run_early(engine: Engine) -> None:
    def pricey(s: Scenario, index: WorldIndex) -> LLMClient:
        return ScriptedLLM([reply_turn("Hello.", cost_usd=0.6)])

    outcomes = run_all(engine, SCENARIOS[:5], pricey, budget=1.0)
    assert len(outcomes) == 2
