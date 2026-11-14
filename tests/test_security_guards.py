import pytest
from sqlalchemy.orm import Session

from parley.backend.services import Backend
from parley.orchestration.router import Specialist
from parley.orchestration.specialists import specialist_registry
from parley.security.guards import GUARD_NAMES, GuardConfig, parse_guards
from parley.tools.catalog import default_registry
from parley.tools.context import ToolContext
from tests.factories import NOW, make_customer


def test_every_guard_is_on_by_default_and_off_turns_all_of_them_off() -> None:
    assert all(getattr(GuardConfig(), name) for name in GUARD_NAMES)
    assert not GuardConfig.off().any_on
    assert GuardConfig().any_on


def test_one_guard_can_be_ablated_and_unknown_names_are_rejected() -> None:
    config = GuardConfig().without("egress")
    assert config.egress is False and config.scan is True
    with pytest.raises(ValueError, match="unknown guard"):
        GuardConfig().without("magic")


def test_settings_parse_into_configs() -> None:
    assert parse_guards("on") == GuardConfig()
    assert parse_guards("off") == GuardConfig.off()
    assert parse_guards("no_scan").scan is False
    with pytest.raises(ValueError, match="unknown guard setting"):
        parse_guards("maybe")


def test_a_locked_ticket_refuses_writes_but_still_reads_and_hands_over(session: Session) -> None:
    sender = make_customer(session, "ada@example.com")
    ctx = ToolContext(Backend(session, lambda: NOW), sender.id, "T-1", write_locked=True)
    registry = default_registry()
    refund = registry.call(
        ctx,
        "issue_refund",
        {"target": "order", "target_id": 1, "amount_cents": 100, "reason": "x"},
    )
    assert refund.error_code == "locked"
    assert registry.call(ctx, "cancel_subscription", {"subscription_id": 1}).error_code == "locked"
    proposals = specialist_registry(Specialist.BILLING)
    assert proposals.call(ctx, "propose_refund", {}).error_code == "locked"
    assert proposals.call(ctx, "propose_cancel_subscription", {}).error_code == "locked"
    note = {"reason": "suspected_injection", "summary": "instructions"}
    assert proposals.call(ctx, "propose_escalation", note).ok
    overview = registry.call(ctx, "get_customer_overview", {})
    assert overview.ok
    handover = registry.call(
        ctx, "escalate_to_human", {"reason": "suspected_injection", "summary": "instructions"}
    )
    assert handover.ok and ctx.escalations[0].reason == "suspected_injection"
