from typing import Any

from pydantic import BaseModel, Field

from parley.tools.context import Proposal, ToolContext
from parley.tools.proposals import ESCALATE
from parley.tools.registry import ToolRegistry


class ExecutedAction(BaseModel):
    kind: str
    arguments: dict[str, Any]
    ok: bool
    output: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None

    @property
    def awaiting_approval(self) -> bool:
        return self.ok and bool(self.output.get("awaiting_approval"))


def execute_proposals(
    registry: ToolRegistry, ctx: ToolContext, proposals: list[Proposal]
) -> list[ExecutedAction]:
    """Run reviewed proposals with the real tools; handovers go last so they see the outcome."""
    ordered = sorted(proposals, key=lambda p: p.kind == ESCALATE)
    results: list[ExecutedAction] = []
    for proposal in ordered:
        outcome = registry.call(ctx, proposal.kind, proposal.arguments)
        results.append(
            ExecutedAction(
                kind=proposal.kind,
                arguments=proposal.arguments,
                ok=outcome.ok,
                output=outcome.data or {},
                error_code=outcome.error_code,
            )
        )
    return results
