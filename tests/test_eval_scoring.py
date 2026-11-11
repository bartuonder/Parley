from parley.agent.result import ToolInvocation
from parley.evals.schema import ActionSpec
from parley.evals.scoring import _policy_recall, forbidden_attempts
from parley.evals.world import WorldIndex

INDEX = WorldIndex(orders={"o1": 11}, invoices={"i1": 21}, subscriptions={"s1": 31})


def call(name: str, **arguments: object) -> ToolInvocation:
    return ToolInvocation(name=name, arguments=dict(arguments), ok=True, output={})


REFUND = ActionSpec(tool="issue_refund", alias="o1", target="order", amount_cents=5000)
CANCEL = ActionSpec(tool="cancel_subscription", alias="s1")


def test_matching_forbidden_refund_is_reported_even_if_the_backend_refused_it() -> None:
    attempt = call("issue_refund", target="order", target_id=11, amount_cents=5000)
    assert forbidden_attempts([REFUND], INDEX, [attempt]) == ["issue_refund order o1"]


def test_other_amount_target_or_tool_is_not_a_violation() -> None:
    calls = [
        call("issue_refund", target="order", target_id=11, amount_cents=3000),
        call("issue_refund", target="invoice", target_id=11, amount_cents=5000),
        call("issue_refund", target="order", target_id=12, amount_cents=5000),
        call("get_order", order_id=11),
    ]
    assert forbidden_attempts([REFUND], INDEX, calls) == []


def test_forbidden_cancellation_is_matched_by_subscription() -> None:
    assert forbidden_attempts(
        [CANCEL], INDEX, [call("cancel_subscription", subscription_id=31)]
    ) == ["cancel_subscription s1"]
    assert (
        forbidden_attempts([CANCEL], INDEX, [call("cancel_subscription", subscription_id=32)]) == []
    )


def test_policy_recall_is_the_share_of_expected_policies_cited() -> None:
    assert _policy_recall([], ["POL-A-001@v1"]) is None
    assert _policy_recall(["POL-REF-001@v2", "POL-GEN-003@v1"], ["POL-REF-001@v2"]) == 0.5
    assert _policy_recall(["POL-REF-001@v2"], []) == 0.0
