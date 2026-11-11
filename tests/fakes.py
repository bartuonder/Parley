import json
from typing import Any

from parley.agent.llm import LLMResponse, Message, ToolCall, Usage
from parley.evals.schema import Scenario
from parley.evals.world import WorldIndex


class ScriptedLLM:
    """Plays back a fixed list of model turns and records what it was asked."""

    def __init__(self, turns: list[LLMResponse]) -> None:
        self._turns = list(turns)
        self.requests: list[list[Message]] = []

    async def complete(self, messages: list[Message], tools: list[dict[str, Any]]) -> LLMResponse:
        self.requests.append([dict(m) for m in messages])
        if not self._turns:
            raise AssertionError("the scripted model ran out of turns")
        return self._turns.pop(0)


def call_turn(
    name: str, arguments_json: str, call_id: str = "c1", cost_usd: float = 0.001
) -> LLMResponse:
    return LLMResponse(
        tool_calls=[ToolCall(id=call_id, name=name, arguments_json=arguments_json)],
        usage=Usage(prompt_tokens=100, completion_tokens=10, cost_usd=cost_usd),
    )


def reply_turn(text: str, cost_usd: float = 0.001) -> LLMResponse:
    return LLMResponse(
        content=text, usage=Usage(prompt_tokens=100, completion_tokens=30, cost_usd=cost_usd)
    )


def reference_llm(scenario: Scenario, index: WorldIndex) -> ScriptedLLM:
    """A model that carries out the scenario's reference solution, then hands over if needed."""
    turns: list[LLMResponse] = []
    for n, action in enumerate(scenario.reference_actions, start=1):
        if action.tool == "cancel_subscription":
            args: dict[str, Any] = {"subscription_id": index.subscriptions[action.alias]}
        else:
            ids = index.orders if action.target == "order" else index.invoices
            args = {
                "target": action.target,
                "target_id": ids[action.alias],
                "amount_cents": action.amount_cents,
                "reason": "reference",
            }
        turns.append(call_turn(action.tool, json.dumps(args), f"c{n}"))
    if scenario.expected.requires_human and not scenario.reference_actions:
        handover = {"reason": "other", "summary": "reference handover"}
        turns.append(call_turn("escalate_to_human", json.dumps(handover), "c-esc"))
    turns.append(reply_turn("Done."))
    return ScriptedLLM(turns)
