from typing import Any

from pydantic import BaseModel

from parley.backend.rules import requires_approval
from parley.backend.services import InvalidRequestError, NotEligibleError, RefundTarget
from parley.db.enums import SubscriptionStatus
from parley.security.limits import check_split
from parley.tools.access import own_invoice, own_order, own_subscription
from parley.tools.context import Proposal, ToolContext
from parley.tools.permissions import Permission
from parley.tools.registry import ToolSpec
from parley.tools.write import CancelSubscriptionParams, EscalateParams, IssueRefundParams

REFUND = "issue_refund"
CANCEL = "cancel_subscription"
ESCALATE = "escalate_to_human"


class Recorded(BaseModel):
    recorded: bool = True
    duplicate: bool = False
    awaiting_approval: bool = False
    note: str = "Recorded. It runs only after review; do not tell the customer it is done yet."


def _record(ctx: ToolContext, kind: str, arguments: dict[str, Any], **extra: bool) -> Recorded:
    proposal = Proposal(kind, arguments)
    duplicate = proposal in ctx.proposals
    if not duplicate:
        ctx.proposals.append(proposal)
    return Recorded(duplicate=duplicate, **extra)


def propose_refund(ctx: ToolContext, params: IssueRefundParams) -> Recorded:
    if params.target == RefundTarget.ORDER:
        own_order(ctx, params.target_id)
        eligibility = ctx.backend.check_order_refund(params.target_id)
    else:
        own_invoice(ctx, params.target_id)
        eligibility = ctx.backend.check_invoice_refund(params.target_id)
    if not eligibility.eligible:
        raise NotEligibleError(eligibility.code)
    if params.amount_cents > eligibility.max_refund_cents:
        raise InvalidRequestError(
            f"amount exceeds refundable maximum of {eligibility.max_refund_cents}"
        )
    arguments = params.model_dump(mode="json")
    if Proposal(REFUND, arguments) not in ctx.proposals:
        prior = sum(
            int(p.arguments["amount_cents"])
            for p in ctx.proposals
            if p.kind == REFUND
            and p.arguments["target"] == arguments["target"]
            and p.arguments["target_id"] == params.target_id
        )
        check_split(ctx, prior, params.amount_cents)
    return _record(
        ctx,
        REFUND,
        params.model_dump(mode="json"),
        awaiting_approval=requires_approval(params.amount_cents),
    )


def propose_cancel_subscription(ctx: ToolContext, params: CancelSubscriptionParams) -> Recorded:
    sub = own_subscription(ctx, params.subscription_id)
    if sub.status == SubscriptionStatus.CANCELLED:
        raise InvalidRequestError("subscription is already cancelled")
    return _record(ctx, CANCEL, params.model_dump(mode="json"))


def propose_escalation(ctx: ToolContext, params: EscalateParams) -> Recorded:
    return _record(ctx, ESCALATE, params.model_dump(mode="json"))


PROPOSAL_TOOLS: list[ToolSpec[Any]] = [
    ToolSpec(
        "propose_refund",
        "Propose refunding an order or invoice of the sender. The request is checked now and "
        "carried out after review. Amounts above the approval threshold also wait for a human.",
        Permission.READ,
        IssueRefundParams,
        propose_refund,
    ),
    ToolSpec(
        "propose_cancel_subscription",
        "Propose cancelling a subscription of the sender at the end of the paid period.",
        Permission.READ,
        CancelSubscriptionParams,
        propose_cancel_subscription,
    ),
    ToolSpec(
        "propose_escalation",
        "Propose handing the ticket to a human with a short note. Use it for legal threats, "
        "suspected fraud, disputed invoices, requests no tool can fulfil, and insistence on "
        "something the policy denies.",
        Permission.READ,
        EscalateParams,
        propose_escalation,
    ),
]
