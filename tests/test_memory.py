from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.orm import Session

from parley.agent.result import ToolInvocation
from parley.memory.facts import decision_facts, facts_from_run
from parley.memory.store import MemoryFact, recall, remember, render_memory
from parley.orchestration.executor import ExecutedAction
from tests.factories import NOW, make_customer


def refund(ok: bool = True, approval: bool = False) -> ExecutedAction:
    return ExecutedAction(
        kind="issue_refund",
        arguments={"target": "order", "target_id": 7, "amount_cents": 4900, "reason": "late"},
        ok=ok,
        output={"awaiting_approval": approval},
    )


def test_facts_are_recalled_newest_first_and_per_customer(session: Session) -> None:
    ada = make_customer(session, "ada@example.com")
    bob = make_customer(session, "bob@example.com")
    remember(session, ada.id, "T-1", [("refund_issued", "first")], NOW)
    remember(session, ada.id, "T-2", [("handover", "second")], NOW + timedelta(days=1))
    remember(session, bob.id, "T-3", [("handover", "other customer")], NOW)
    facts = recall(session, ada.id)
    assert [f.content for f in facts] == ["second", "first"]
    assert recall(session, bob.id)[0].content == "other customer"


def test_recall_is_limited(session: Session) -> None:
    ada = make_customer(session, "ada@example.com")
    remember(session, ada.id, "T-1", [("k", f"fact {i}") for i in range(5)], NOW)
    assert len(recall(session, ada.id, limit=3)) == 3


def test_memory_renders_as_dated_bullets() -> None:
    fact = MemoryFact(
        kind="handover",
        content="Handed over to a human (legal_threat)",
        ticket_id="T-9",
        created_at=datetime(2026, 5, 20, 9, tzinfo=UTC),
    )
    assert render_memory([fact]) == "- 2026-05-20 (T-9): Handed over to a human (legal_threat)"


def test_facts_come_from_actions_and_refusals_only() -> None:
    escalate = ExecutedAction(
        kind="escalate_to_human",
        arguments={"reason": "legal_threat", "summary": "free text from the ticket"},
        ok=True,
    )
    cancel = ExecutedAction(kind="cancel_subscription", arguments={"subscription_id": 3}, ok=True)
    denied = ToolInvocation(
        name="propose_refund",
        arguments={"target": "order", "target_id": 9, "amount_cents": 100, "reason": "x"},
        ok=False,
        output={"error_code": "not_eligible", "message": "window_expired"},
    )
    facts = facts_from_run([refund(), refund(approval=True), cancel, escalate], [denied])
    kinds = [k for k, _ in facts]
    assert kinds == [
        "refund_issued",
        "refund_pending",
        "cancellation",
        "handover",
        "refund_denied",
    ]
    text_blob = " ".join(c for _, c in facts)
    assert "free text from the ticket" not in text_blob
    assert "window_expired" in text_blob and "$49.00" in text_blob


def test_failed_actions_and_other_errors_leave_no_fact() -> None:
    other = ToolInvocation(
        name="propose_refund", arguments={}, ok=False, output={"error_code": "access_denied"}
    )
    assert facts_from_run([refund(ok=False)], [other]) == []


def test_reseeding_clears_memory(session: Session) -> None:
    from parley.seed.runner import reset_database

    ada = make_customer(session, "ada@example.com")
    remember(session, ada.id, "T-1", [("handover", "x")], NOW)
    reset_database(session)
    count = session.execute(text("SELECT count(*) FROM customer_memory")).scalar_one()
    assert count == 0


def test_human_decisions_become_facts() -> None:
    waiting = refund(approval=True)
    waiting.output["id"] = 12
    approved = decision_facts([waiting], {"12": True})
    declined = decision_facts([waiting], {"12": False})
    assert approved == [
        ("refund_approved", "Refund of $49.00 for order 7 was approved by a human and processed")
    ]
    assert declined[0][0] == "refund_declined"
    assert decision_facts([waiting], {}) == declined
