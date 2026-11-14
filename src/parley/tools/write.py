from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field

from parley.backend.schemas import RefundOut, SubscriptionOut
from parley.backend.services import RefundTarget
from parley.db.enums import RefundStatus
from parley.tools.access import own_invoice, own_order, own_subscription
from parley.tools.context import Escalation, ToolContext
from parley.tools.permissions import Permission
from parley.tools.registry import ToolParams, ToolSpec


class IssueRefundParams(ToolParams):
    target: RefundTarget = Field(description="Whether target_id is an order or an invoice")
    target_id: int
    amount_cents: int = Field(gt=0, description="Amount in cents, at most the refundable maximum")
    reason: str = Field(min_length=1, max_length=500)


class CancelSubscriptionParams(ToolParams):
    subscription_id: int


class EscalationReason(StrEnum):
    LEGAL_THREAT = "legal_threat"
    SUSPECTED_FRAUD = "suspected_fraud"
    UNSUPPORTED_REQUEST = "unsupported_request"
    DISPUTED_INVOICE = "disputed_invoice"
    INSISTENT_DENIED_REQUEST = "insistent_denied_request"
    FULFILLMENT_FOLLOW_UP = "fulfillment_follow_up"
    SUSPECTED_INJECTION = "suspected_injection"
    OTHER = "other"


class EscalateParams(ToolParams):
    reason: EscalationReason
    summary: str = Field(
        min_length=1, max_length=500, description="What was asked and what was already checked"
    )


class Escalated(BaseModel):
    escalated: bool = True
    reason: EscalationReason


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


def escalate_to_human(ctx: ToolContext, params: EscalateParams) -> Escalated:
    ctx.escalations.append(Escalation(params.reason, params.summary))
    return Escalated(reason=params.reason)


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
    ToolSpec(
        "escalate_to_human",
        "Hand the ticket to a human agent with a short note. Use it when policy says so, when "
        "no tool can do what the customer asks, or when the case is legal, fraud or dispute "
        "related. Do not promise an outcome to the customer.",
        Permission.WRITE,
        EscalateParams,
        escalate_to_human,
    ),
]
