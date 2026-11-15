import logging
import os
from typing import Any, Protocol

# In DEV mode litellm copies .env into os.environ on import, which would bypass our settings.
os.environ.setdefault("LITELLM_MODE", "PRODUCTION")

import litellm
from pydantic import BaseModel, Field

from parley.settings import get_settings

logger = logging.getLogger(__name__)

Message = dict[str, Any]


class ToolCall(BaseModel):
    id: str
    name: str
    arguments_json: str


class Usage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cached_tokens: int = 0
    cost_usd: float = 0.0

    def __add__(self, other: "Usage") -> "Usage":
        return Usage(
            prompt_tokens=self.prompt_tokens + other.prompt_tokens,
            completion_tokens=self.completion_tokens + other.completion_tokens,
            cached_tokens=self.cached_tokens + other.cached_tokens,
            cost_usd=self.cost_usd + other.cost_usd,
        )


class LLMResponse(BaseModel):
    content: str | None = None
    tool_calls: list[ToolCall] = Field(default_factory=list)
    usage: Usage = Field(default_factory=Usage)

    def as_message(self) -> Message:
        message: Message = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            message["tool_calls"] = [
                {
                    "id": c.id,
                    "type": "function",
                    "function": {"name": c.name, "arguments": c.arguments_json},
                }
                for c in self.tool_calls
            ]
        return message


class LLMClient(Protocol):
    async def complete(self, messages: list[Message], tools: list[dict[str, Any]]) -> LLMResponse:
        """One model turn; `tools` use the OpenAI function-calling schema."""
        ...


class LiteLLMClient:
    def __init__(self, model: str | None = None, api_key: str | None = None) -> None:
        settings = get_settings()
        self.model = model or settings.agent_model
        secret = settings.llm_api_key
        self._api_key = api_key or (secret.get_secret_value() if secret else None)

    async def complete(self, messages: list[Message], tools: list[dict[str, Any]]) -> LLMResponse:
        response = await litellm.acompletion(
            model=self.model,
            messages=messages,
            tools=tools or None,
            temperature=0,
            api_key=self._api_key,
            timeout=60,
            num_retries=2,
        )
        return to_response(response)


def to_response(response: Any) -> LLMResponse:
    message = response.choices[0].message
    calls = [
        ToolCall(id=c.id, name=c.function.name, arguments_json=c.function.arguments or "{}")
        for c in (message.tool_calls or [])
    ]
    return LLMResponse(content=message.content, tool_calls=calls, usage=_usage(response))


def _usage(response: Any) -> Usage:
    raw = getattr(response, "usage", None)
    try:
        cost = float(litellm.completion_cost(completion_response=response))
    except Exception:
        logger.warning("no price known for model %s", getattr(response, "model", "?"))
        cost = 0.0
    details = getattr(raw, "prompt_tokens_details", None)
    return Usage(
        prompt_tokens=getattr(raw, "prompt_tokens", 0) or 0,
        completion_tokens=getattr(raw, "completion_tokens", 0) or 0,
        cached_tokens=getattr(details, "cached_tokens", 0) or 0,
        cost_usd=cost,
    )
