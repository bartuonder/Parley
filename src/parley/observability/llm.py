from typing import Any

from parley.agent.llm import LLMClient, LLMResponse, Message
from parley.observability.tracing import span


class TracedLLM:
    """Records every model call as a span with tokens, cost and the model name."""

    def __init__(self, inner: LLMClient) -> None:
        self._inner = inner

    @property
    def model(self) -> str:
        return str(getattr(self._inner, "model", "unknown"))

    async def complete(self, messages: list[Message], tools: list[dict[str, Any]]) -> LLMResponse:
        with span("llm.complete", "llm", model=self.model, messages=len(messages)) as handle:
            response = await self._inner.complete(messages, tools)
            usage = response.usage
            handle.set(
                prompt_tokens=usage.prompt_tokens,
                completion_tokens=usage.completion_tokens,
                cached_tokens=usage.cached_tokens,
                cost_usd=usage.cost_usd,
                tool_calls=len(response.tool_calls),
            )
            return response
