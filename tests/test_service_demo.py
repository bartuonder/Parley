import json
from typing import Any

import pytest

import parley.service.demo as demo
from parley.service.demo import DEMO_TICKETS, describe, run_ticket


def test_the_demo_tickets_cover_a_refund_an_approval_and_an_attack() -> None:
    assert [t.key for t in DEMO_TICKETS] == ["refund", "approval", "injection"]
    assert len({t.sender_email for t in DEMO_TICKETS}) == 3


def test_a_ticket_is_followed_until_it_stops(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, str, Any]] = []
    states = iter(["queued", "running", "resolved"])

    def fake(base: str, key: str, method: str, path: str, body: Any = None) -> dict[str, Any]:
        calls.append((method, path, body))
        status = "queued" if method == "POST" else next(states)
        return {"id": "T-1", "status": status, "cost_usd": 0.004, "latency_s": 6.0, "result": {}}

    monkeypatch.setattr(demo, "call", fake)
    monkeypatch.setattr(demo.time, "sleep", lambda s: None)
    result = run_ticket("http://x", "", DEMO_TICKETS[0])
    assert result["status"] == "resolved"
    assert calls[0][0] == "POST" and json.dumps(calls[0][2]).count("order 95") == 1
    assert [c[1] for c in calls[1:]] == ["/tickets/T-1"] * 3


def test_the_summary_lists_the_actions_taken() -> None:
    result = {
        "status": "resolved",
        "cost_usd": 0.0041,
        "latency_s": 7.0,
        "result": {"actions": [{"name": "get_order"}, {"name": "issue_refund"}]},
    }
    text = describe(DEMO_TICKETS[0], result)
    assert "resolved" in text and "get_order, issue_refund" in text and "$0.0041" in text
