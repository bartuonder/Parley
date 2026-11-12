import json
import time
from typing import Any

from parley.agent.llm import LLMClient, Message, Usage
from parley.agent.prompt import render_ticket, system_prompt
from parley.agent.result import AgentResult, EscalationRecord, StopReason, ToolInvocation
from parley.agent.ticket import Ticket
from parley.agent.toolbox import Toolbox, open_toolbox
from parley.tools.context import ToolContext
from parley.tools.registry import ToolRegistry


async def run_ticket(
    llm: LLMClient,
    registry: ToolRegistry,
    ctx: ToolContext,
    ticket: Ticket,
    *,
    model: str,
    max_steps: int,
    max_cost_usd: float,
    system: str | None = None,
    notes: str = "",
) -> AgentResult:
    """Run the tool-calling loop for one ticket on behalf of the sender in `ctx`."""
    started = time.perf_counter()
    rendered = render_ticket(ticket.id, ticket.sender_email, ticket.subject, ticket.body)
    user_text = "\n\n".join(part for part in (rendered, notes) if part)
    messages: list[Message] = [
        {"role": "system", "content": system or system_prompt(ctx.backend.now().date())},
        {"role": "user", "content": user_text},
    ]
    usage = Usage()
    trace: list[ToolInvocation] = []
    reply, stop, steps = "", StopReason.MAX_STEPS, 0

    async with open_toolbox(registry, ctx) as box:
        while steps < max_steps:
            steps += 1
            response = await llm.complete(messages, box.schemas)
            usage = usage + response.usage
            messages.append(response.as_message())
            if not response.tool_calls:
                reply, stop = (response.content or "").strip(), StopReason.REPLY
                break
            if usage.cost_usd >= max_cost_usd:
                stop = StopReason.BUDGET
                break
            for call in response.tool_calls:
                invocation, text = await _invoke(box, call.name, call.arguments_json)
                trace.append(invocation)
                messages.append({"role": "tool", "tool_call_id": call.id, "content": text})

    return AgentResult(
        ticket_id=ticket.id,
        model=model,
        reply=reply,
        stop_reason=stop,
        steps=steps,
        latency_s=time.perf_counter() - started,
        usage=usage,
        tool_calls=trace,
        escalations=[EscalationRecord(reason=e.reason, summary=e.summary) for e in ctx.escalations],
    )


async def _invoke(box: Toolbox, name: str, arguments_json: str) -> tuple[ToolInvocation, str]:
    arguments = _parse_arguments(arguments_json)
    if arguments is None:
        text = json.dumps(
            {"ok": False, "error_code": "invalid_arguments", "message": "arguments are not JSON"}
        )
        failed = ToolInvocation(
            name=name,
            arguments={},
            ok=False,
            output={"error_code": "invalid_arguments", "message": "arguments are not JSON"},
        )
        return failed, text
    return await box.call(name, arguments)


def _parse_arguments(raw: str) -> dict[str, Any] | None:
    try:
        value = json.loads(raw or "{}")
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None
