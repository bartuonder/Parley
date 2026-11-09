from parley.backend.services import Backend, BackendError, RefundTarget
from parley.evals.schema import ActionSpec
from parley.evals.world import WorldIndex


def apply_action(backend: Backend, index: WorldIndex, action: ActionSpec, key: str) -> None:
    """Run one scenario action through the backend; raises BackendError if it is refused."""
    if action.tool == "cancel_subscription":
        backend.cancel_subscription(index.subscriptions[action.alias])
        return
    if action.target == "order":
        target, target_id = RefundTarget.ORDER, index.orders[action.alias]
    else:
        target, target_id = RefundTarget.INVOICE, index.invoices[action.alias]
    backend.issue_refund(target, target_id, action.amount_cents or 0, "eval action", key)


def apply_all(
    backend: Backend, index: WorldIndex, actions: list[ActionSpec], scenario_id: str
) -> None:
    for n, action in enumerate(actions, start=1):
        apply_action(backend, index, action, f"{scenario_id}-action-{n}")


def is_refused(backend: Backend, index: WorldIndex, action: ActionSpec, key: str) -> bool:
    """True when the backend rejects the action, which proves a denial is rule-correct."""
    try:
        apply_action(backend, index, action, key)
    except BackendError:
        return True
    return False
