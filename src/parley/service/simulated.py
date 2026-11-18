import asyncio
from typing import Any

from parley.agent.llm import LLMResponse, Message, ToolCall, Usage
from parley.orchestration.router import ROUTER_PROMPT

CRITIC_PREFIX = "You review a support specialist"


class SimulatedLLM:
    """A model stand-in with fixed answers and a set delay, for demos, CI and load tests."""

    def __init__(self, latency_s: float = 0.0) -> None:
        self.latency_s = latency_s
        self.model = "simulated"

    async def complete(self, messages: list[Message], tools: list[dict[str, Any]]) -> LLMResponse:
        if self.latency_s:
            await asyncio.sleep(self.latency_s)
        usage = Usage(prompt_tokens=400, completion_tokens=40, cost_usd=0.0001)
        system = str(messages[0].get("content", "")) if messages else ""
        if system.startswith(ROUTER_PROMPT[:40]):
            return LLMResponse(content="billing", usage=usage)
        if system.startswith(CRITIC_PREFIX):
            return LLMResponse(content='{"approved": true, "issues": []}', usage=usage)
        if tools and not any(m.get("role") == "tool" for m in messages):
            call = ToolCall(id="sim-1", name="get_customer_overview", arguments_json="{}")
            return LLMResponse(tool_calls=[call], usage=usage)
        text = "Thanks for writing in. I looked at your account and a colleague will follow up."
        return LLMResponse(content=text, usage=usage)
