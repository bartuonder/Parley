from typing import Any

from pydantic import BaseModel, Field, computed_field

from parley.agent.result import AgentResult, StopReason, ToolInvocation
from parley.db.enums import RefundStatus
from parley.evals.schema import ActionSpec, Scenario, StateDiff
from parley.evals.state import Snapshot, diff_snapshots, normalize
from parley.evals.world import WorldIndex
from parley.orchestration.claims import unbacked_claims


class TraceEntry(BaseModel):
    name: str
    arguments: dict[str, Any]
    ok: bool
    error_code: str | None = None


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
    trace: list[TraceEntry] = Field(default_factory=list)
    unbacked_claims: list[str] = Field(default_factory=list)
    specialist: str | None = None
    revisions: int = 0
    awaiting_approval: bool = False
    error: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def handover_ok(self) -> bool:
        return self.handover_expected == self.handover_actual

    @computed_field  # type: ignore[prop-decorator]
    @property
    def success(self) -> bool:
        return self.state_ok and self.replied and self.error is None

    @classmethod
    def failed(cls, scenario: Scenario, error: str) -> "ScenarioOutcome":
        """Outcome for a run that crashed before producing a result."""
        return cls(
            scenario_id=scenario.id,
            category=scenario.category,
            difficulty=scenario.difficulty,
            tags=scenario.tags,
            state_ok=False,
            handover_expected=scenario.expected.requires_human,
            handover_actual=False,
            replied=False,
            policy_recall=None if not scenario.expected.policy_refs else 0.0,
            stop_reason=StopReason.ERROR,
            steps=0,
            tool_calls=[],
            tool_errors=0,
            cost_usd=0.0,
            latency_s=0.0,
            prompt_tokens=0,
            completion_tokens=0,
            reply="",
            actual_diff=StateDiff(),
            error=error,
        )


def score(
    scenario: Scenario,
    index: WorldIndex,
    before: Snapshot,
    after: Snapshot,
    result: AgentResult,
) -> ScenarioOutcome:
    actual = diff_snapshots(before, after)
    pending = any(r.status == RefundStatus.PENDING_APPROVAL for r in actual.new_refunds)
    done = {c.name for c in result.tool_calls if c.ok}
    handed_over = bool(result.escalations) or pending
    unbacked = unbacked_claims(
        result.reply,
        refunded="issue_refund" in done,
        cancelled="cancel_subscription" in done,
        handed_over=handed_over,
    )
    return ScenarioOutcome(
        scenario_id=scenario.id,
        category=scenario.category,
        difficulty=scenario.difficulty,
        tags=scenario.tags,
        state_ok=normalize(actual) == normalize(scenario.expected.diff),
        forbidden_attempts=forbidden_attempts(scenario.forbidden_actions, index, result.tool_calls),
        handover_expected=scenario.expected.requires_human,
        handover_actual=handed_over,
        replied=bool(result.reply) and result.stop_reason == StopReason.REPLY,
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
        unbacked_claims=sorted(c.value for c in unbacked),
        specialist=result.extras.get("specialist"),
        revisions=int(result.extras.get("revisions", 0)),
        awaiting_approval=bool(result.extras.get("awaiting_approval", False)),
        trace=[
            TraceEntry(
                name=c.name,
                arguments=c.arguments,
                ok=c.ok,
                error_code=None if c.ok else str(c.output.get("error_code")),
            )
            for c in result.tool_calls
        ],
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
