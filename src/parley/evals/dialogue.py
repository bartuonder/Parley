from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from parley.agent.llm import LLMClient, Usage
from parley.agent.result import AgentResult, StopReason
from parley.agent.ticket import Ticket
from parley.evals.schema import DialogueSpec
from parley.evals.simulator import Turn, next_customer_move, render_transcript

RunTurn = Callable[[Ticket], Awaitable[AgentResult]]


@dataclass(frozen=True)
class DialogueRun:
    result: AgentResult
    turns: list[Turn]
    simulator_usage: Usage


def thread_ticket(opening: Ticket, turns: list[Turn]) -> Ticket:
    """The ticket for the next agent run: the newest customer message first, then the history."""
    history = render_transcript(turns[:-1])
    body = f"{turns[-1].text}\n\nEarlier in this conversation:\n{history}"
    return opening.model_copy(update={"body": body})


def merge_results(results: list[AgentResult]) -> AgentResult:
    """One result for the whole dialogue: every reply and call counts, the last turn decides."""
    last = results[-1]
    usage = Usage()
    for r in results:
        usage = usage + r.usage
    return last.model_copy(
        update={
            "reply": "\n\n".join(r.reply for r in results if r.reply),
            "steps": sum(r.steps for r in results),
            "latency_s": sum(r.latency_s for r in results),
            "usage": usage,
            "tool_calls": [c for r in results for c in r.tool_calls],
            "escalations": [e for r in results for e in r.escalations],
            "extras": {
                **last.extras,
                "turns": len(results),
                "awaiting_approval": any(r.extras.get("awaiting_approval") for r in results),
            },
        }
    )


async def run_dialogue(
    spec: DialogueSpec, opening: Ticket, simulator: LLMClient, run_turn: RunTurn
) -> DialogueRun:
    """Alternate agent replies and simulated customer messages until the customer is done."""
    turns = [Turn("customer", opening.body)]
    results: list[AgentResult] = []
    simulator_usage = Usage()
    ticket = opening
    for number in range(1, spec.max_turns + 1):
        result = await run_turn(ticket)
        results.append(result)
        if result.reply:
            turns.append(Turn("support", result.reply))
        if result.stop_reason != StopReason.REPLY or number == spec.max_turns:
            break
        move = await next_customer_move(simulator, spec, turns)
        simulator_usage = simulator_usage + move.usage
        if move.done:
            break
        turns.append(Turn("customer", move.message))
        ticket = thread_ticket(opening, turns)
    return DialogueRun(merge_results(results), turns, simulator_usage)
