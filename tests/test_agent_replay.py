import asyncio
import json
from typing import Any

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from parley.agent.llm import LLMClient, LLMResponse, Message
from parley.evals.agent_run import (
    MAX_CONSECUTIVE_ERRORS,
    Architecture,
    LLMFactory,
    evaluate,
    run_scenario,
)
from parley.evals.loader import load_scenarios, load_set
from parley.evals.schema import Scenario
from parley.evals.scoring import ScenarioOutcome
from parley.evals.world import WorldIndex
from parley.orchestration.router import CATEGORY_SPECIALIST
from tests.fakes import (
    ScriptedLLM,
    call_turn,
    reference_llm,
    reference_multi_llm,
    reply_turn,
    router_for,
)

SCENARIOS = [
    *load_scenarios(),
    *load_set("heldout"),
    *load_set("dialogue"),
    *load_set("redteam"),
]
MODEL = "scripted"
MAX_STEPS = 8
MAX_COST = 1.0


def no_retriever(_: Session) -> None:
    return None


def finished_customer() -> ScriptedLLM:
    return ScriptedLLM([reply_turn('{"message": "", "done": true}')])


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
            simulator=finished_customer(),
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
    assert outcome.writes_executed == outcome.writes_correct == len(scenario.reference_actions)
    assert outcome.ticket_text.strip() and "{" not in outcome.ticket_text
    assert outcome.writes_found == outcome.writes_expected


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
    assert outcome.tool_errors == 1 and outcome.writes_executed == 0


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


def test_run_aborts_after_repeated_crashes(engine: Engine) -> None:
    class Down:
        async def complete(
            self, messages: list[Message], tools: list[dict[str, Any]]
        ) -> LLMResponse:
            raise RuntimeError("no credits")

    outcomes = run_all(engine, SCENARIOS[:10], lambda s, i: Down(), budget=5.0)
    assert len(outcomes) == MAX_CONSECUTIVE_ERRORS


def test_a_reply_that_claims_an_unperformed_refund_is_flagged(session: Session) -> None:
    scenario = next(s for s in SCENARIOS if s.id == "REF-001")

    def liar(s: Scenario, index: WorldIndex) -> LLMClient:
        return ScriptedLLM([reply_turn("I have processed the refund for you.")])

    outcome = play(session, scenario, liar)
    assert not outcome.state_ok
    assert outcome.unbacked_claims == ["refund"]


def test_a_backed_refund_claim_is_not_flagged(session: Session) -> None:
    scenario = next(s for s in SCENARIOS if s.id == "REF-001")

    def honest(s: Scenario, index: WorldIndex) -> LLMClient:
        llm = reference_llm(s, index)
        llm._turns[-1] = reply_turn("We have processed the refund.")
        return llm

    outcome = play(session, scenario, honest)
    assert outcome.success and outcome.unbacked_claims == []


MULTI = Architecture(name="multi", router_llm_factory=router_for)


@pytest.mark.parametrize("scenario", SCENARIOS, ids=[s.id for s in SCENARIOS])
def test_reference_plan_scores_perfectly_through_the_multi_agent_graph(
    scenario: Scenario, session: Session
) -> None:
    outcome = asyncio.run(
        run_scenario(
            session,
            scenario,
            reference_multi_llm,
            no_retriever,
            model=MODEL,
            max_steps=MAX_STEPS,
            max_cost_usd=MAX_COST,
            arch=MULTI,
            simulator=finished_customer(),
        )
    )
    assert outcome.state_ok and outcome.success and outcome.error is None
    assert outcome.handover_ok and outcome.forbidden_attempts == []
    assert outcome.unbacked_claims == [] and outcome.revisions == 0
    assert outcome.writes_correct == outcome.writes_executed == outcome.writes_found
    assert outcome.specialist == CATEGORY_SPECIALIST[scenario.category.value].value


def test_the_multi_architecture_needs_a_router(session: Session) -> None:
    scenario = SCENARIOS[0]
    with pytest.raises(ValueError, match="router"):
        asyncio.run(
            run_scenario(
                session,
                scenario,
                reference_multi_llm,
                no_retriever,
                model=MODEL,
                max_steps=MAX_STEPS,
                max_cost_usd=MAX_COST,
                arch=Architecture(name="multi"),
            )
        )
