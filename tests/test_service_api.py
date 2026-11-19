import json
import time
from collections.abc import Iterator
from contextlib import contextmanager

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from parley.backend.rules import APPROVAL_THRESHOLD_CENTS
from parley.db.enums import OrderStatus, ShipmentStatus
from parley.service.api import create_app
from parley.service.runtime import Runtime
from parley.service.simulated import SimulatedLLM
from tests.factories import NOW, make_customer, make_item, make_order, make_shipment
from tests.fakes import ScriptedLLM, call_turn, reply_turn
from tests.test_service_core import APPROVE, service

BODY = {"sender_email": "ada@example.com", "subject": "Hello", "body": "Where is my parcel?"}


def runtime_for(session: Session, svc: object) -> Runtime:
    @contextmanager
    def sessions() -> Iterator[Session]:
        yield session

    from parley.service.core import TicketService

    assert isinstance(svc, TicketService)
    return Runtime(svc, sessions)


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    make_customer(session, "ada@example.com")
    app = create_app(runtime_for(session, service(session, SimulatedLLM())), api_key="secret")
    with TestClient(app, headers={"X-API-Key": "secret"}) as test_client:
        yield test_client


def wait_for(client: TestClient, ticket_id: str, status: str) -> dict[str, object]:
    for _ in range(100):
        body: dict[str, object] = client.get(f"/tickets/{ticket_id}").json()
        if body["status"] == status:
            return body
        time.sleep(0.05)
    raise AssertionError(f"{ticket_id} never reached {status}")


def test_health_is_open_and_everything_else_needs_the_key(client: TestClient) -> None:
    assert client.get("/health", headers={"X-API-Key": ""}).json() == {"status": "ok"}
    assert client.get("/tickets", headers={"X-API-Key": "wrong"}).status_code == 401
    assert client.get("/tickets", headers={"X-API-Key": ""}).status_code == 401
    assert client.get("/tickets").status_code == 200


def test_a_ticket_is_accepted_then_resolved_and_listed(client: TestClient) -> None:
    created = client.post("/tickets", json=BODY)
    assert created.status_code == 202 and created.json()["status"] == "queued"
    ticket_id = created.json()["id"]
    done = wait_for(client, ticket_id, "resolved")
    assert (
        str(done["reply"]).startswith("Thanks for writing in") and done["specialist"] == "billing"
    )
    assert [t["id"] for t in client.get("/tickets?status=resolved").json()] == [ticket_id]
    stats = client.get("/stats").json()
    assert stats["by_status"] == {"resolved": 1} and stats["total_cost_usd"] > 0


def test_bad_requests_get_clear_errors(client: TestClient) -> None:
    assert (
        client.post("/tickets", json={**BODY, "sender_email": "nobody@example.com"}).status_code
        == 422
    )
    assert client.post("/tickets", json={**BODY, "sender_email": "not-an-email"}).status_code == 422
    assert client.post("/tickets", json={**BODY, "body": ""}).status_code == 422
    assert client.get("/tickets/T-missing").status_code == 404
    assert client.get("/tickets/T-missing/events").status_code == 404
    assert client.post("/approvals/T-missing/decision", json={"decisions": {}}).status_code == 404


def test_the_event_stream_replays_node_events_and_ends(client: TestClient) -> None:
    ticket_id = client.post("/tickets", json=BODY).json()["id"]
    wait_for(client, ticket_id, "resolved")
    seen: list[tuple[str, dict[str, object]]] = []
    with client.stream("GET", f"/tickets/{ticket_id}/events") as response:
        assert response.headers["content-type"].startswith("text/event-stream")
        name = ""
        for line in response.iter_lines():
            if line.startswith("event: "):
                name = line[7:]
            elif line.startswith("data: "):
                seen.append((name, json.loads(line[6:])))
    kinds = [k for k, _ in seen]
    assert kinds[0] == "queued" and kinds[-1] == "end" and "node" in kinds
    assert seen[-1][1] == {"status": "resolved"}
    first_id = next(d["id"] for k, d in seen if k == "queued")
    with client.stream(
        "GET", f"/tickets/{ticket_id}/events", headers={"Last-Event-ID": str(first_id)}
    ) as response:
        assert "event: queued" not in "".join(response.iter_lines())


def test_a_large_refund_shows_up_in_the_approval_queue_and_can_be_decided(
    session: Session,
) -> None:
    sender = make_customer(session, "ada@example.com")
    amount = APPROVAL_THRESHOLD_CENTS + 5000
    order = make_order(session, sender, total_cents=amount)
    make_item(session, order, unit_price_cents=amount)
    make_shipment(session, order, status=ShipmentStatus.DELIVERED, delivered_at=NOW)
    order.status = OrderStatus.DELIVERED
    session.flush()
    args = {"target": "order", "target_id": order.id, "amount_cents": amount, "reason": "late"}
    llm = ScriptedLLM(
        [
            call_turn("propose_refund", json.dumps(args)),
            reply_turn("Draft."),
            reply_turn(APPROVE),
            reply_turn("Your refund is under review."),
        ]
    )
    svc = service(session, llm, ScriptedLLM([reply_turn("shipping")]))
    with TestClient(create_app(runtime_for(session, svc), api_key=None)) as client:
        ticket_id = client.post("/tickets", json=BODY).json()["id"]
        wait_for(client, ticket_id, "awaiting_approval")
        waiting = client.get("/approvals").json()
        assert [w["id"] for w in waiting] == [ticket_id]
        refund_id = str(waiting[0]["pending"][0]["refund_id"])
        decided = client.post(
            f"/approvals/{ticket_id}/decision", json={"decisions": {refund_id: False}}
        )
        assert decided.status_code == 200 and decided.json()["status"] == "resolved"
        assert "declined" in decided.json()["followup"]
        again = client.post(f"/approvals/{ticket_id}/decision", json={"decisions": {}})
        assert again.status_code == 409 and client.get("/approvals").json() == []


def test_tickets_carry_a_number_the_customers_name_and_policy_titles(client: TestClient) -> None:
    first = client.post("/tickets", json=BODY).json()
    second = client.post("/tickets", json={**BODY, "subject": "Again"}).json()
    assert second["number"] == first["number"] + 1 and first["number"] >= 1001
    done = wait_for(client, first["id"], "resolved")
    assert done["customer_name"] == "Ada Lovelace" and done["sender_email"] == "ada@example.com"
    assert done["policies"] == []
    listed = client.get("/tickets").json()
    assert [t["number"] for t in listed] == sorted((t["number"] for t in listed), reverse=True)


def test_known_policy_keys_are_shown_with_their_titles_and_unknown_ones_are_dropped(
    client: TestClient, session: Session
) -> None:
    from parley.service.tables import ServiceTicketRow

    ticket_id = client.post("/tickets", json=BODY).json()["id"]
    wait_for(client, ticket_id, "resolved")
    row = session.get(ServiceTicketRow, ticket_id)
    assert row is not None
    row.result = {"policies": ["POL-REF-001@v2", "POL-XXX-999@v1"]}
    session.flush()
    shown = client.get(f"/tickets/{ticket_id}").json()["policies"]
    assert [p["id"] for p in shown] == ["POL-REF-001"] and shown[0]["version"] == 2
    assert shown[0]["title"]


def test_the_customer_list_and_the_approval_threshold_are_exposed(client: TestClient) -> None:
    customers = client.get("/customers").json()
    assert {"name": "Ada Lovelace", "email": "ada@example.com"} in customers
    assert client.get("/stats").json()["approval_threshold_cents"] == APPROVAL_THRESHOLD_CENTS
