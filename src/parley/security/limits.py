from parley.backend.rules import APPROVAL_THRESHOLD_CENTS
from parley.backend.services import InvalidRequestError
from parley.tools.context import ToolContext

SPLIT_MESSAGE = (
    "Refunds for this order or invoice in this ticket add up to more than the approval "
    "threshold. Do not split a refund to avoid approval; hand the ticket to a human."
)


def check_split(ctx: ToolContext, prior_cents: int, amount_cents: int) -> None:
    """Reject a later refund that only stays under the threshold because the total was split."""
    if not ctx.guards.limits or prior_cents == 0:
        return
    total = prior_cents + amount_cents
    if total > APPROVAL_THRESHOLD_CENTS and amount_cents <= APPROVAL_THRESHOLD_CENTS:
        raise InvalidRequestError(SPLIT_MESSAGE)
