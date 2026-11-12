from parley.agent.result import ToolInvocation
from parley.orchestration.executor import ExecutedAction
from parley.orchestration.responder import money
from parley.tools.proposals import CANCEL, ESCALATE, REFUND


def facts_from_run(
    actions: list[ExecutedAction], proposal_calls: list[ToolInvocation]
) -> list[tuple[str, str]]:
    """Facts to keep, built only from what the tools did or refused, never from ticket text."""
    facts: list[tuple[str, str]] = []
    for action in actions:
        if not action.ok:
            continue
        args = action.arguments
        if action.kind == REFUND:
            amount = money(int(args["amount_cents"]))
            what = f"Refund of {amount} for {args['target']} {args['target_id']}"
            kind, state = (
                ("refund_pending", "is waiting for human approval")
                if action.awaiting_approval
                else ("refund_issued", "was processed")
            )
            facts.append((kind, f"{what} {state}"))
        elif action.kind == CANCEL:
            facts.append(("cancellation", f"Subscription {args['subscription_id']} set to cancel"))
        elif action.kind == ESCALATE:
            facts.append(("handover", f"Handed over to a human ({args['reason']})"))
    for call in proposal_calls:
        if (
            call.name == "propose_refund"
            and not call.ok
            and call.output.get("error_code") == "not_eligible"
        ):
            args = call.arguments
            facts.append(
                (
                    "refund_denied",
                    f"Refund for {args.get('target')} {args.get('target_id')} was refused "
                    f"({call.output.get('message')})",
                )
            )
    return facts
