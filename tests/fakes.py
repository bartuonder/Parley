from typing import Any

from parley.agent.llm import LLMResponse, Message, ToolCall, Usage


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
