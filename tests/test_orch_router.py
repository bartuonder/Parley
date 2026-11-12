import asyncio

import pytest

from parley.agent.ticket import Ticket
from parley.orchestration.router import (
    DEFAULT_SPECIALIST,
    ROUTER_PROMPT,
    Specialist,
    parse_label,
    route_ticket,
)
from tests.fakes import ScriptedLLM, reply_turn

TICKET = Ticket(id="T-1", sender_email="ada@example.com", subject="Parcel", body="Where is it?")


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("shipping", Specialist.SHIPPING),
        ("  Subscription.\n", Specialist.SUBSCRIPTION),
        ("billing", Specialist.BILLING),
        ("I think this is shipping, not billing", Specialist.SHIPPING),
        ("unclear", DEFAULT_SPECIALIST),
        (None, DEFAULT_SPECIALIST),
        ("", DEFAULT_SPECIALIST),
    ],
)
def test_labels_are_parsed_with_a_safe_default(text: str | None, expected: Specialist) -> None:
    assert parse_label(text) == expected


def test_router_asks_with_the_ticket_and_returns_usage() -> None:
    llm = ScriptedLLM([reply_turn("shipping", cost_usd=0.0002)])
    decision = asyncio.run(route_ticket(llm, TICKET))
    assert decision.specialist == Specialist.SHIPPING
    assert decision.usage.cost_usd == pytest.approx(0.0002)
    system, user = llm.requests[0]
    assert system["content"] == ROUTER_PROMPT
    assert "<ticket_body>\nWhere is it?\n</ticket_body>" in user["content"]
