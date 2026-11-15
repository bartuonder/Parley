import json
import time
from typing import Any

from parley.agent.llm import LLMClient, Message, Usage
from parley.agent.prompt import render_ticket, system_prompt
from parley.agent.result import AgentResult, EscalationRecord, StopReason, ToolInvocation
from parley.agent.ticket import Ticket
from parley.agent.toolbox import Toolbox, open_toolbox
from parley.security.egress import guard_reply
from parley.security.screen import screen_ticket, screen_tool_output
from parley.security.spotlight import new_token, with_note, wrap_untrusted
from parley.tools.context import ToolContext
from parley.tools.registry import ToolRegistry
from parley.tools.write import EscalationReason


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
    final: bool = True,
) -> AgentResult:
    """Run the tool-calling loop for one ticket on behalf of the sender in `ctx`."""
    started = time.perf_counter()
    screen_ticket(ctx, ticket.subject, ticket.body)
    fence = new_token() if ctx.guards.spotlight else None
    rendered = render_ticket(ticket.id, ticket.sender_email, ticket.subject, ticket.body, fence)
    user_text = "\n\n".join(part for part in (rendered, notes) if part)
    base_system = system or system_prompt(ctx.backend.now().date())
    messages: list[Message] = [
        {"role": "system", "content": with_note(base_system, fence is not None)},
        {"role": "user", "content": user_text},
    ]
    usage = Usage()
    trace: list[ToolInvocation] = []
    reply, stop, steps = "", StopReason.MAX_STEPS, 0

    async with open_toolbox(registry, ctx) as box:
        if ctx.prefetch_overview and "get_customer_overview" in {s.name for s in registry.specs}:
            invocation, text = await _invoke(box, OVERVIEW, "{}")
            trace.append(invocation)
            screen_tool_output(ctx, OVERVIEW, text)
            content = wrap_untrusted("tool_output", text, fence) if fence else text
            messages += _prefetched(content)
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
                screen_tool_output(ctx, call.name, text)
                content = wrap_untrusted("tool_output", text, fence) if fence else text
                messages.append({"role": "tool", "tool_call_id": call.id, "content": content})

    if final:
        reply = _finalize(registry, ctx, reply)
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
        extras={"guard_events": list(ctx.guard_events)},
    )


OVERVIEW = "get_customer_overview"
PREFETCH_CALL_ID = "prefetch-overview"


def _prefetched(content: str) -> list[Message]:
    """The overview as if the model had asked for it, so the conversation stays well formed."""
    call = {"name": OVERVIEW, "arguments": "{}"}
    return [
        {
            "role": "assistant",
            "content": None,
            "tool_calls": [{"id": PREFETCH_CALL_ID, "type": "function", "function": call}],
        },
        {"role": "tool", "tool_call_id": PREFETCH_CALL_ID, "content": content},
    ]


HANDOVER_NOTE = "A colleague from our team will follow up on this request."


def _finalize(registry: ToolRegistry, ctx: ToolContext, reply: str) -> str:
    """Guard steps of a final reply: hand a locked ticket to a human, then check the text."""
    names = {spec.name for spec in registry.specs}
    if ctx.write_locked and not ctx.escalations and "escalate_to_human" in names:
        registry.call(
            ctx,
            "escalate_to_human",
            {
                "reason": EscalationReason.SUSPECTED_INJECTION,
                "summary": "The ticket contains instructions aimed at the assistant.",
            },
        )
        reply = f"{reply} {HANDOVER_NOTE}".strip()
    if ctx.guards.egress and reply:
        reply, events = guard_reply(ctx, reply)
        ctx.guard_events.extend(events)
    return reply


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
