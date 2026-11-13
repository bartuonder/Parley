import time
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.types import Command

from parley.agent.llm import LLMClient, Usage
from parley.agent.result import AgentResult, EscalationRecord, StopReason, ToolInvocation
from parley.agent.ticket import Ticket
from parley.orchestration.executor import ExecutedAction
from parley.orchestration.graph import GraphDeps, Switches, build_graph
from parley.tools.catalog import default_registry
from parley.tools.context import ToolContext


async def run_multi(
    router_llm: LLMClient,
    llm: LLMClient,
    ctx: ToolContext,
    ticket: Ticket,
    *,
    model: str,
    max_steps: int,
    max_cost_usd: float,
    max_revisions: int,
    checkpointer: BaseCheckpointSaver[Any] | None = None,
    switches: Switches | None = None,
) -> AgentResult:
    """Run the multi-agent graph for one ticket; a paused approval still returns the reply."""
    started = time.perf_counter()
    deps = _deps(
        router_llm,
        llm,
        ctx,
        model,
        max_steps=max_steps,
        max_cost_usd=max_cost_usd,
        max_revisions=max_revisions,
        switches=switches,
    )
    graph = build_graph(checkpointer or InMemorySaver())
    state = await graph.ainvoke({"ticket": ticket.model_dump()}, config=_config(ticket, deps))
    return to_result(state, ticket, ctx, model, time.perf_counter() - started)


async def resume_multi(
    router_llm: LLMClient,
    llm: LLMClient,
    ctx: ToolContext,
    ticket: Ticket,
    decisions: dict[str, bool],
    *,
    model: str,
    max_steps: int,
    max_cost_usd: float,
    max_revisions: int,
    checkpointer: BaseCheckpointSaver[Any],
) -> AgentResult:
    """Apply human decisions to a paused ticket; the result carries the follow-up message."""
    started = time.perf_counter()
    deps = _deps(
        router_llm,
        llm,
        ctx,
        model,
        max_steps=max_steps,
        max_cost_usd=max_cost_usd,
        max_revisions=max_revisions,
    )
    graph = build_graph(checkpointer)
    state = await graph.ainvoke(Command(resume=decisions), config=_config(ticket, deps))
    return to_result(state, ticket, ctx, model, time.perf_counter() - started)


def _deps(
    router_llm: LLMClient,
    llm: LLMClient,
    ctx: ToolContext,
    model: str,
    *,
    max_steps: int,
    max_cost_usd: float,
    max_revisions: int,
    switches: Switches | None = None,
) -> GraphDeps:
    return GraphDeps(
        router_llm=router_llm,
        llm=llm,
        ctx=ctx,
        registry=default_registry(),
        model=model,
        max_steps=max_steps,
        max_cost_usd=max_cost_usd,
        max_revisions=max_revisions,
        switches=switches or Switches(),
    )


def _config(ticket: Ticket, deps: GraphDeps) -> Any:
    return {"configurable": {"thread_id": ticket.id, "deps": deps}}


def to_result(
    state: dict[str, Any], ticket: Ticket, ctx: ToolContext, model: str, latency_s: float
) -> AgentResult:
    actions = [ExecutedAction.model_validate(a) for a in state.get("actions", [])]
    investigated = [ToolInvocation.model_validate(c) for c in state.get("trace", [])]
    executed = [
        ToolInvocation(
            name=a.kind,
            arguments=a.arguments,
            ok=a.ok,
            output=a.output if a.ok else {"error_code": a.error_code},
        )
        for a in actions
    ]
    reply = state.get("reply", "")
    return AgentResult(
        ticket_id=ticket.id,
        model=model,
        reply=reply,
        stop_reason=StopReason.REPLY if reply else StopReason.ERROR,
        steps=int(state.get("steps", 0)),
        latency_s=latency_s,
        usage=Usage.model_validate(state.get("usage") or {}),
        tool_calls=[*investigated, *executed],
        escalations=[EscalationRecord(reason=e.reason, summary=e.summary) for e in ctx.escalations],
        extras={
            "specialist": state.get("specialist"),
            "revisions": int(state.get("revisions", 0)),
            "critic_issues": state.get("issues", []),
            "awaiting_approval": "__interrupt__" in state,
            "followup": state.get("followup", ""),
            "critic_source": state.get("verdict", {}).get("source"),
            "unbacked_after_rewrite": state.get("unbacked", []),
        },
    )
