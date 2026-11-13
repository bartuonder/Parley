import asyncio
import json

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from parley.agent.llm import LLMClient, LLMResponse
from parley.agent.result import AgentResult, StopReason, ToolInvocation
from parley.agent.ticket import Ticket
from parley.evals.agent_run import LLMFactory, evaluate, run_scenario
from parley.evals.dialogue import merge_results, run_dialogue, thread_ticket
from parley.evals.loader import load_scenarios
from parley.evals.schema import DialogueSpec, Scenario
from parley.evals.scoring import ScenarioOutcome
from parley.evals.simulator import SIMULATOR_PROMPT, Turn, next_customer_move
from parley.evals.world import WorldIndex
from tests.fakes import ScriptedLLM, reference_llm, reply_turn

SPEC = DialogueSpec(
    persona="Impatient and short.",
    goal="Return the lamp.",
    facts=["The lamp is the item to return"],
    max_turns=3,
)
OPENING = Ticket(
    id="T-1", sender_email="a@example.com", subject="Return", body="I want to return it."
)


def move(message: str, done: bool = False, cost: float = 0.001) -> LLMResponse:
    return reply_turn(json.dumps({"message": message, "done": done}), cost_usd=cost)


def agent_result(reply: str, calls: list[str] | None = None, **extras: object) -> AgentResult:
    return AgentResult(
        ticket_id="T-1",
        model="m",
        reply=reply,
        stop_reason=StopReason.REPLY,
        steps=1,
        latency_s=1.0,
        tool_calls=[ToolInvocation(name=n, arguments={}, ok=True, output={}) for n in calls or []],
        extras=dict(extras),
    )


def test_the_simulator_prompt_carries_persona_and_facts_and_reads_the_move() -> None:
    llm = ScriptedLLM([move("The lamp, please.")])
    turns = [Turn("customer", "I want to return it."), Turn("support", "Which item?")]
    result = asyncio.run(next_customer_move(llm, SPEC, turns))
    assert (result.message, result.done) == ("The lamp, please.", False)
    system, user = llm.requests[0]
    assert (
        "Impatient and short." in system["content"] and "The lamp is the item" in system["content"]
    )
    assert "[support] Which item?" in user["content"]
    assert "{persona}" not in system["content"] and "{persona}" in SIMULATOR_PROMPT


def test_an_unreadable_or_empty_move_ends_the_dialogue() -> None:
    for text in ("no json here", '{"message": "hi"}', '{"message": "", "done": false}'):
        result = asyncio.run(next_customer_move(ScriptedLLM([reply_turn(text)]), SPEC, []))
        assert result.done and result.message == ""


def test_the_next_ticket_leads_with_the_newest_message_and_keeps_the_history() -> None:
    turns = [Turn("customer", "First."), Turn("support", "Which?"), Turn("customer", "The lamp.")]
    ticket = thread_ticket(OPENING, turns)
    assert ticket.id == OPENING.id and ticket.body.startswith("The lamp.")
    assert "[customer] First.\n[support] Which?" in ticket.body


def test_results_merge_into_one_whole_dialogue() -> None:
    first = agent_result("Which item?", awaiting_approval=False)
    second = agent_result("Refunded.", ["issue_refund"], awaiting_approval=True)
    merged = merge_results([first, second])
    assert merged.reply == "Which item?\n\nRefunded."
    assert [c.name for c in merged.tool_calls] == ["issue_refund"]
    assert merged.steps == 2 and merged.latency_s == 2.0
    assert merged.extras["turns"] == 2 and merged.extras["awaiting_approval"] is True


def test_the_dialogue_stops_when_the_customer_is_done_or_the_turn_limit_is_reached() -> None:
    seen: list[str] = []

    async def run_turn(ticket: Ticket) -> AgentResult:
        seen.append(ticket.body)
        return agent_result(f"Reply {len(seen)}.")

    done = asyncio.run(
        run_dialogue(
            SPEC, OPENING, ScriptedLLM([move("More.", cost=0.5), move("", True)]), run_turn
        )
    )
    assert len(seen) == 2 and done.simulator_usage.cost_usd == pytest.approx(0.501)
    assert [t.role for t in done.turns] == ["customer", "support", "customer", "support"]

    seen.clear()
    endless = ScriptedLLM([move("Again."), move("Again."), move("Again.")])
    capped = asyncio.run(run_dialogue(SPEC, OPENING, endless, run_turn))
    assert len(seen) == SPEC.max_turns and capped.result.extras["turns"] == 3


def test_a_failed_turn_ends_the_dialogue_without_asking_the_customer() -> None:
    async def broken(ticket: Ticket) -> AgentResult:
        return agent_result("").model_copy(update={"stop_reason": StopReason.ERROR})

    result = asyncio.run(run_dialogue(SPEC, OPENING, ScriptedLLM([]), broken))
    assert result.result.stop_reason == StopReason.ERROR and len(result.turns) == 1


def dialogue_scenario() -> Scenario:
    base = next(s for s in load_scenarios() if s.id == "REF-001")
    return base.model_copy(update={"dialogue": SPEC})


def play(session: Session, simulator: LLMClient | None, llm_for: LLMFactory) -> ScenarioOutcome:
    return asyncio.run(
        run_scenario(
            session,
            dialogue_scenario(),
            llm_for,
            lambda _: None,
            model="scripted",
            max_steps=8,
            max_cost_usd=1.0,
            simulator=simulator,
        )
    )


def test_a_scenario_dialogue_is_scored_on_the_final_state(session: Session) -> None:
    def asks_first(s: Scenario, index: WorldIndex) -> ScriptedLLM:
        llm = reference_llm(s, index)
        llm._turns.insert(0, reply_turn("Which item do you mean?"))
        return llm

    outcome = play(
        session, ScriptedLLM([move("The lamp.", cost=0.002), move("", True)]), asks_first
    )
    assert outcome.state_ok and outcome.success and outcome.turns == 2
    assert outcome.transcript[0].startswith("[customer]")
    assert len(outcome.transcript) == 4
    assert outcome.simulator_cost_usd == pytest.approx(0.003)


def test_a_dialogue_scenario_needs_a_simulator(session: Session) -> None:
    with pytest.raises(ValueError, match="user simulator"):
        play(session, None, reference_llm)


def test_simulator_cost_counts_against_the_total_budget(engine: Engine) -> None:
    scenarios = [dialogue_scenario().model_copy(update={"id": f"DLG-00{n}"}) for n in (1, 2, 3)]
    sim = ScriptedLLM([move("", True, cost=0.6)] * 3)
    outcomes = asyncio.run(
        evaluate(
            engine,
            scenarios,
            reference_llm,
            lambda _: None,
            model="scripted",
            max_steps=8,
            max_cost_usd=1.0,
            total_budget_usd=1.0,
            simulator=sim,
        )
    )
    assert len(outcomes) == 2
