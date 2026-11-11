from typing import Any

from pydantic import Field

from parley.backend.schemas import RefundOut, SubscriptionOut
from parley.backend.services import RefundTarget
from parley.db.enums import RefundStatus
from parley.tools.access import own_invoice, own_order, own_subscription
from parley.tools.context import ToolContext
from parley.tools.permissions import Permission
from parley.tools.registry import ToolParams, ToolSpec


class IssueRefundParams(ToolParams):
    target: RefundTarget = Field(description="Whether target_id is an order or an invoice")
    target_id: int
    amount_cents: int = Field(gt=0, description="Amount in cents, at most the refundable maximum")
    reason: str = Field(min_length=1, max_length=500)


class CancelSubscriptionParams(ToolParams):
    subscription_id: int


class RefundResult(RefundOut):
    created: bool
    awaiting_approval: bool


def refund_key(ctx: ToolContext, params: IssueRefundParams) -> str:
    """Derived from the request so a retry of the same refund replays instead of paying twice."""
    return f"{ctx.ticket_id}:{params.target}:{params.target_id}:{params.amount_cents}"


def issue_refund(ctx: ToolContext, params: IssueRefundParams) -> RefundResult:
    if params.target == RefundTarget.ORDER:
        own_order(ctx, params.target_id)
    else:
        own_invoice(ctx, params.target_id)
    refund, created = ctx.backend.issue_refund(
        params.target,
        params.target_id,
        params.amount_cents,
        params.reason,
        refund_key(ctx, params),
    )
    base = RefundOut.model_validate(refund)
    return RefundResult(
        **base.model_dump(),
        created=created,
        awaiting_approval=refund.status == RefundStatus.PENDING_APPROVAL,
    )


def cancel_subscription(ctx: ToolContext, params: CancelSubscriptionParams) -> SubscriptionOut:
    own_subscription(ctx, params.subscription_id)
    sub = ctx.backend.cancel_subscription(params.subscription_id)
    return SubscriptionOut.model_validate(sub)


WRITE_TOOLS: list[ToolSpec[Any]] = [
    ToolSpec(
        "issue_refund",
        "Refund an order or invoice of the sender. Check eligibility first. Amounts above the "
        "approval threshold are created as pending approval and take effect only after a human "
        "approves them. Repeating the same request is safe.",
        Permission.RISKY,
        IssueRefundParams,
        issue_refund,
    ),
    ToolSpec(
        "cancel_subscription",
        "Schedule cancellation of a subscription of the sender at the end of the paid period. "
        "The plan stays active until then. Repeating the call changes nothing.",
        Permission.WRITE,
        CancelSubscriptionParams,
        cancel_subscription,
    ),
]
