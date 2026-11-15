import asyncio

from sqlalchemy.orm import Session

from parley.evals.agent_run import Architecture, run_scenario
from parley.evals.loader import load_scenarios
from parley.evals.schema import Scenario
from parley.evals.world import WorldIndex
from tests.fakes import ScriptedLLM, reply_turn, router_for

APPROVE = '{"approved": true, "issues": []}'
SCENARIO = next(s for s in load_scenarios() if s.id == "REF-013")


def test_critic_and_responder_can_run_on_their_own_models(session: Session) -> None:
    specialist = ScriptedLLM([reply_turn("Draft: it is on its way.")])
    critic = ScriptedLLM([reply_turn(APPROVE)])
    responder = ScriptedLLM([reply_turn("Your order is on its way.")])
    arch = Architecture(
        name="multi",
        router_llm_factory=router_for,
        critic_llm_factory=lambda s, i: critic,
        responder_llm_factory=lambda s, i: responder,
    )
    outcome = asyncio.run(
        run_scenario(
            session,
            SCENARIO,
            lambda s, i: specialist,
            lambda _: None,
            model="m",
            max_steps=8,
            max_cost_usd=1.0,
            arch=arch,
        )
    )
    assert outcome.error is None and outcome.reply == "Your order is on its way."
    assert len(specialist.requests) == 1 and len(critic.requests) == 1
    assert len(responder.requests) == 1
    assert "Draft: it is on its way." in responder.requests[0][1]["content"]


def test_without_role_models_one_client_serves_all_three_roles(session: Session) -> None:
    only = ScriptedLLM([reply_turn("Draft."), reply_turn(APPROVE), reply_turn("Hello.")])

    def factory(s: Scenario, i: WorldIndex) -> ScriptedLLM:
        return only

    arch = Architecture(name="multi", router_llm_factory=router_for)
    asyncio.run(
        run_scenario(
            session,
            SCENARIO,
            factory,
            lambda _: None,
            model="m",
            max_steps=8,
            max_cost_usd=1.0,
            arch=arch,
        )
    )
    assert len(only.requests) == 3
