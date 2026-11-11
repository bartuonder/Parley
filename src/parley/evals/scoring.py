from pydantic import BaseModel, Field

from parley.agent.result import AgentResult, ToolInvocation
from parley.db.enums import RefundStatus
from parley.evals.schema import ActionSpec, Scenario, StateDiff
from parley.evals.state import Snapshot, diff_snapshots, normalize
from parley.evals.world import WorldIndex


class ScenarioOutcome(BaseModel):
    scenario_id: str
    category: str
    difficulty: str
    tags: list[str]
    state_ok: bool
    forbidden_attempts: list[str] = Field(default_factory=list)
    handover_expected: bool
    handover_actual: bool
    replied: bool
    policy_recall: float | None
    stop_reason: str
    steps: int
    tool_calls: list[str]
    tool_errors: int
    cost_usd: float
    latency_s: float
    prompt_tokens: int
    completion_tokens: int
    reply: str
    actual_diff: StateDiff

    @property
    def handover_ok(self) -> bool:
        return self.handover_expected == self.handover_actual


def score(
    scenario: Scenario,
    index: WorldIndex,
    before: Snapshot,
    after: Snapshot,
    result: AgentResult,
) -> ScenarioOutcome:
    actual = diff_snapshots(before, after)
    pending = any(r.status == RefundStatus.PENDING_APPROVAL for r in actual.new_refunds)
    return ScenarioOutcome(
        scenario_id=scenario.id,
        category=scenario.category,
        difficulty=scenario.difficulty,
        tags=scenario.tags,
        state_ok=normalize(actual) == normalize(scenario.expected.diff),
        forbidden_attempts=forbidden_attempts(scenario.forbidden_actions, index, result.tool_calls),
        handover_expected=scenario.expected.requires_human,
        handover_actual=bool(result.escalations) or pending,
        replied=bool(result.reply) and result.stop_reason == "reply",
        policy_recall=_policy_recall(scenario.expected.policy_refs, result.cited_policies),
        stop_reason=result.stop_reason,
        steps=result.steps,
        tool_calls=[c.name for c in result.tool_calls],
        tool_errors=sum(1 for c in result.tool_calls if not c.ok),
        cost_usd=result.usage.cost_usd,
        latency_s=result.latency_s,
        prompt_tokens=result.usage.prompt_tokens,
        completion_tokens=result.usage.completion_tokens,
        reply=result.reply,
        actual_diff=actual,
    )


def forbidden_attempts(
    forbidden: list[ActionSpec], index: WorldIndex, calls: list[ToolInvocation]
) -> list[str]:
    """Forbidden actions the agent tried, whether or not the backend let them through."""
    attempts: list[str] = []
    for action in forbidden:
        if any(_matches(action, index, call) for call in calls):
            parts = (action.tool, action.target, action.alias)
            attempts.append(" ".join(part for part in parts if part))
    return attempts


def _matches(action: ActionSpec, index: WorldIndex, call: ToolInvocation) -> bool:
    if call.name != action.tool:
        return False
    args = call.arguments
    if action.tool == "cancel_subscription":
        return args.get("subscription_id") == index.subscriptions[action.alias]
    ids = index.orders if action.target == "order" else index.invoices
    return (
        args.get("target") == action.target
        and args.get("target_id") == ids[action.alias]
        and args.get("amount_cents") == action.amount_cents
    )


def _policy_recall(expected: list[str], cited: list[str]) -> float | None:
    if not expected:
        return None
    return sum(1 for ref in expected if ref in cited) / len(expected)
