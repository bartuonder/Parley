import asyncio
import os
import subprocess
import sys
from types import SimpleNamespace
from typing import Any

import pytest

from parley.agent.llm import LiteLLMClient, LLMResponse, ToolCall, Usage, to_response


def fake_response(
    content: str | None, calls: list[tuple[str, str, str]] | None = None
) -> SimpleNamespace:
    tool_calls = [
        SimpleNamespace(id=i, function=SimpleNamespace(name=n, arguments=a))
        for i, n, a in calls or []
    ]
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    usage = SimpleNamespace(prompt_tokens=100, completion_tokens=20)
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage, model="m")


def test_usage_adds_up() -> None:
    total = Usage(prompt_tokens=1, completion_tokens=2, cost_usd=0.5) + Usage(
        prompt_tokens=3, completion_tokens=4, cost_usd=0.25
    )
    assert (total.prompt_tokens, total.completion_tokens, total.cost_usd) == (4, 6, 0.75)


def test_response_with_tool_calls_round_trips_to_an_assistant_message() -> None:
    response = LLMResponse(
        content=None, tool_calls=[ToolCall(id="c1", name="get_order", arguments_json='{"a": 1}')]
    )
    message = response.as_message()
    assert message["role"] == "assistant" and message["content"] is None
    assert message["tool_calls"][0]["function"] == {"name": "get_order", "arguments": '{"a": 1}'}


def test_plain_reply_has_no_tool_calls_key() -> None:
    assert "tool_calls" not in LLMResponse(content="hello").as_message()


def test_to_response_reads_text_calls_and_usage(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("litellm.completion_cost", lambda completion_response: 0.0012)
    raw = fake_response("ok", [("c1", "get_order", '{"order_id": 3}')])
    response = to_response(raw)
    assert response.content == "ok"
    assert [(c.id, c.name, c.arguments_json) for c in response.tool_calls] == [
        ("c1", "get_order", '{"order_id": 3}')
    ]
    assert response.usage == Usage(prompt_tokens=100, completion_tokens=20, cost_usd=0.0012)


def test_unknown_model_price_falls_back_to_zero_cost(monkeypatch: pytest.MonkeyPatch) -> None:
    def no_price(completion_response: Any) -> float:
        raise ValueError("unmapped model")

    monkeypatch.setattr("litellm.completion_cost", no_price)
    assert to_response(fake_response("ok")).usage.cost_usd == 0.0


def test_client_sends_the_configured_model_and_key(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, Any] = {}

    async def fake_acompletion(**kwargs: Any) -> SimpleNamespace:
        seen.update(kwargs)
        return fake_response("hi")

    monkeypatch.setattr("litellm.acompletion", fake_acompletion)
    monkeypatch.setattr("litellm.completion_cost", lambda completion_response: 0.0)
    client = LiteLLMClient(model="test-model", api_key="sk-test")
    response = asyncio.run(client.complete([{"role": "user", "content": "x"}], []))
    assert response.content == "hi"
    assert seen["model"] == "test-model" and seen["api_key"] == "sk-test"
    assert seen["tools"] is None and seen["temperature"] == 0


def test_importing_the_client_does_not_load_dotenv_into_the_environment() -> None:
    code = (
        "import os, parley.agent.llm; "
        "print(os.environ.get('LITELLM_MODE'), os.environ.get('PARLEY_FIXED_NOW'))"
    )
    env = {k: v for k, v in os.environ.items() if k not in ("LITELLM_MODE", "PARLEY_FIXED_NOW")}
    out = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True)
    assert out.stdout.split() == ["PRODUCTION", "None"], out.stderr
