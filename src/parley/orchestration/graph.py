from dataclasses import dataclass, field
from typing import Any, Literal, TypedDict

from langchain_core.runnables import RunnableConfig
from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from langgraph.types import interrupt

from parley.agent.llm import LLMClient, Usage
from parley.agent.loop import run_ticket
from parley.agent.result import StopReason, ToolInvocation
from parley.agent.ticket import Ticket
from parley.memory.facts import decision_facts, facts_from_run
from parley.memory.store import recall, remember, render_memory
from parley.orchestration.critic import review
from parley.orchestration.executor import ExecutedAction, execute_proposals
from parley.orchestration.responder import money, respond
from parley.orchestration.router import Specialist, route_ticket
from parley.orchestration.specialists import specialist_prompt, specialist_registry
from parley.tools.context import Proposal, ToolContext
from parley.tools.proposals import ESCALATE
from parley.tools.registry import ToolRegistry


class GraphState(TypedDict, total=False):
    ticket: dict[str, Any]
    specialist: str
    route_raw: str
    draft: str
    proposals: list[dict[str, Any]]
    trace: list[dict[str, Any]]
    revisions: int
    verdict: dict[str, Any]
    feedback: str
    issues: list[str]
    actions: list[dict[str, Any]]
    reply: str
    unbacked: list[str]
    followup: str
    usage: dict[str, Any]
    steps: int
    stop_reason: str


@dataclass(frozen=True)
class Switches:
    """Parts of the pipeline that an ablation can turn off."""

    critic: bool = True
    rewrite: bool = True
    route: bool = True


@dataclass
class GraphDeps:
    router_llm: LLMClient
    llm: LLMClient
    ctx: ToolContext
    registry: ToolRegistry
    model: str
    max_steps: int
    max_cost_usd: float
    max_revisions: int
    switches: Switches = field(default_factory=Switches)


def _deps(config: RunnableConfig) -> GraphDeps:
    deps: GraphDeps = config["configurable"]["deps"]
    return deps


def _usage(state: GraphState, extra: Usage) -> dict[str, Any]:
    return (Usage.model_validate(state.get("usage") or {}) + extra).model_dump()


def _proposals(state: GraphState) -> list[Proposal]:
    return [Proposal(p["kind"], p["arguments"]) for p in state.get("proposals", [])]


def _actions(state: GraphState) -> list[ExecutedAction]:
    return [ExecutedAction.model_validate(a) for a in state.get("actions", [])]


async def triage(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    deps = _deps(config)
    if not deps.switches.route:
        return {"specialist": Specialist.BILLING.value, "route_raw": "fixed"}
    decision = await route_ticket(deps.router_llm, Ticket.model_validate(state["ticket"]))
    return {
        "specialist": decision.specialist.value,
        "route_raw": decision.raw,
        "usage": _usage(state, decision.usage),
    }


async def investigate(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    deps = _deps(config)
    ctx = deps.ctx
    ctx.proposals.clear()
    specialist = Specialist(state["specialist"])
    memory = render_memory(recall(ctx.backend.session, ctx.customer_id))
    result = await run_ticket(
        deps.llm,
        specialist_registry(specialist),
        ctx,
        Ticket.model_validate(state["ticket"]),
        model=deps.model,
        max_steps=deps.max_steps,
        max_cost_usd=deps.max_cost_usd,
        system=specialist_prompt(specialist, ctx.backend.now().date(), memory),
        notes=state.get("feedback", ""),
    )
    proposals = [{"kind": p.kind, "arguments": p.arguments} for p in ctx.proposals]
    update: dict[str, Any] = {
        "draft": result.reply,
        "proposals": proposals,
        "trace": [c.model_dump() for c in result.tool_calls],
        "usage": _usage(state, result.usage),
        "steps": state.get("steps", 0) + result.steps,
        "stop_reason": result.stop_reason.value,
    }
    if result.stop_reason != StopReason.REPLY:
        update["proposals"] = [_handover("The specialist did not finish within its limits.")]
    return update


def _handover(summary: str) -> dict[str, Any]:
    return {"kind": ESCALATE, "arguments": {"reason": "other", "summary": summary}}


async def critic(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    deps = _deps(config)
    if not deps.switches.critic:
        return {"verdict": {"approved": True, "issues": [], "source": "skipped"}, "issues": []}
    calls = [ToolInvocation.model_validate(c) for c in state.get("trace", [])]
    verdict = await review(
        deps.llm,
        Ticket.model_validate(state["ticket"]),
        _proposals(state),
        state.get("draft", ""),
        calls,
    )
    update: dict[str, Any] = {
        "verdict": verdict.model_dump(exclude={"usage"}),
        "usage": _usage(state, verdict.usage),
        "issues": verdict.issues,
    }
    if not verdict.approved:
        update["feedback"] = verdict.feedback()
        update["revisions"] = state.get("revisions", 0) + 1
    return update


def after_critic(
    state: GraphState, config: RunnableConfig
) -> Literal["investigate", "handover", "execute"]:
    if state.get("verdict", {}).get("approved"):
        return "execute"
    if state.get("revisions", 0) <= _deps(config).max_revisions:
        return "investigate"
    return "handover"


async def handover(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    issues = "; ".join(state.get("issues", []))
    note = (
        f"The reviewer could not approve the plan after {state.get('revisions', 0)} tries: {issues}"
    )
    return {"proposals": [_handover(note[:500])]}


async def execute(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    deps = _deps(config)
    done = execute_proposals(deps.registry, deps.ctx, _proposals(state))
    return {"actions": [a.model_dump() for a in done]}


async def respond_node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    deps = _deps(config)
    final = await respond(
        deps.llm,
        Ticket.model_validate(state["ticket"]),
        state.get("draft", ""),
        _actions(state),
        rewrite=deps.switches.rewrite,
    )
    return {"reply": final.text, "unbacked": final.unbacked, "usage": _usage(state, final.usage)}


async def remember_node(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    ctx = _deps(config).ctx
    calls = [ToolInvocation.model_validate(c) for c in state.get("trace", [])]
    proposal_calls = [c for c in calls if c.name.startswith("propose_")]
    facts = facts_from_run(_actions(state), proposal_calls)
    if facts:
        remember(
            ctx.backend.session, ctx.customer_id, state["ticket"]["id"], facts, ctx.backend.now()
        )
        ctx.backend.session.commit()
    return {}


def after_remember(state: GraphState) -> str:
    return "approval" if any(a.awaiting_approval for a in _actions(state)) else END


async def approval(state: GraphState, config: RunnableConfig) -> dict[str, Any]:
    """Pause until a human decides each waiting refund, then apply the decisions."""
    deps = _deps(config)
    waiting = [a for a in _actions(state) if a.awaiting_approval]
    decisions: dict[str, bool] = interrupt(
        {
            "ticket_id": state["ticket"]["id"],
            "refunds": [
                {
                    "refund_id": a.output["id"],
                    "amount": money(int(a.arguments["amount_cents"])),
                    "target": f"{a.arguments['target']} {a.arguments['target_id']}",
                }
                for a in waiting
            ],
        }
    )
    lines = []
    for action in waiting:
        refund_id = int(action.output["id"])
        approved = bool(decisions.get(str(refund_id), False))
        deps.ctx.backend.resolve_refund(refund_id, approve=approved)
        verdict = "approved and processed" if approved else "declined"
        lines.append(
            f"Your refund of {money(int(action.arguments['amount_cents']))} was {verdict}."
        )
    remember(
        deps.ctx.backend.session,
        deps.ctx.customer_id,
        state["ticket"]["id"],
        decision_facts(waiting, decisions),
        deps.ctx.backend.now(),
    )
    deps.ctx.backend.session.commit()
    return {"followup": " ".join(lines)}


def build_graph(
    checkpointer: BaseCheckpointSaver[Any] | None = None,
) -> CompiledStateGraph[Any, Any, Any, Any]:
    builder = StateGraph(GraphState)
    builder.add_node("triage", triage)
    builder.add_node("investigate", investigate)
    builder.add_node("critic", critic)
    builder.add_node("handover", handover)
    builder.add_node("execute", execute)
    builder.add_node("respond", respond_node)
    builder.add_node("remember", remember_node)
    builder.add_node("approval", approval)

    builder.add_edge(START, "triage")
    builder.add_edge("triage", "investigate")
    builder.add_edge("investigate", "critic")
    builder.add_conditional_edges("critic", after_critic)
    builder.add_edge("handover", "execute")
    builder.add_edge("execute", "respond")
    builder.add_edge("respond", "remember")
    builder.add_conditional_edges("remember", after_remember)
    builder.add_edge("approval", END)
    return builder.compile(checkpointer=checkpointer)
