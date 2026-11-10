from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from parley.backend.api import create_app, get_backend
from parley.backend.services import Backend
from parley.db.enums import OrderStatus, ShipmentStatus
from parley.db.models import Order
from tests.factories import (
    NOW,
    make_customer,
    make_item,
    make_order,
    make_shipment,
    make_subscription,
)

CLOCK = NOW + timedelta(days=10)


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_backend] = lambda: Backend(session, lambda: CLOCK)
    yield TestClient(app)


def delivered_order(session: Session, price: int = 5000) -> Order:
    order = make_order(session, make_customer(session), total_cents=price)
    make_item(session, order, unit_price_cents=price)
    make_shipment(session, order, status=ShipmentStatus.DELIVERED, delivered_at=NOW)
    order.status = OrderStatus.DELIVERED
    session.flush()
    return order


def test_health(client: TestClient) -> None:
    assert client.get("/health").json() == {"status": "ok"}


def test_customer_lookup_and_get(session: Session, client: TestClient) -> None:
    customer = make_customer(session, "ada@example.com")
    by_email = client.get("/customers/lookup", params={"email": "ADA@example.com"})
    assert by_email.status_code == 200
    assert by_email.json()["id"] == customer.id
    assert client.get(f"/customers/{customer.id}").json()["tier"] == "standard"


def test_unknown_customer_returns_404_with_code(client: TestClient) -> None:
    response = client.get("/customers/999")
    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


def test_orders_include_items_shipments_and_refunds(session: Session, client: TestClient) -> None:
    order = delivered_order(session)
    body = client.get(f"/customers/{order.customer_id}/orders").json()
    assert len(body) == 1
    assert body[0]["items"][0]["sku"] == "SKU-1"
    assert body[0]["shipments"][0]["status"] == "delivered"
    assert body[0]["refunds"] == []


def test_shipment_lookup_by_tracking_number(session: Session, client: TestClient) -> None:
    delivered_order(session)
    response = client.get("/shipments/TRK-1")
    assert response.status_code == 200
    assert response.json()["carrier"] == "DHL"
    assert client.get("/shipments/missing").status_code == 404


def test_order_refund_eligibility_endpoint(session: Session, client: TestClient) -> None:
    order = delivered_order(session)
    body = client.get(f"/orders/{order.id}/refund-eligibility").json()
    assert body == {"eligible": True, "code": "eligible", "max_refund_cents": 5000}


def test_subscription_and_invoice_reads(session: Session, client: TestClient) -> None:
    customer = make_customer(session)
    sub = make_subscription(session, customer)
    assert client.get(f"/subscriptions/{sub.id}").json()["plan"] == "pro"
    subs = client.get(f"/customers/{customer.id}/subscriptions").json()
    assert [s["id"] for s in subs] == [sub.id]
    assert client.get(f"/customers/{customer.id}/invoices").json() == []
    assert client.get("/invoices/999/refund-eligibility").status_code == 404


def refund_body(order_id: int, amount: int = 5000, key: str = "k1") -> dict[str, object]:
    return {
        "target": "order",
        "target_id": order_id,
        "amount_cents": amount,
        "reason": "damaged",
        "idempotency_key": key,
    }


def test_issue_refund_creates_then_replays(session: Session, client: TestClient) -> None:
    order = delivered_order(session)
    first = client.post("/refunds", json=refund_body(order.id))
    second = client.post("/refunds", json=refund_body(order.id))
    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert first.json()["status"] == "processed"
    assert client.get(f"/orders/{order.id}").json()["status"] == "refunded"


def test_refund_with_reused_key_for_other_amount_conflicts(
    session: Session, client: TestClient
) -> None:
    order = delivered_order(session)
    client.post("/refunds", json=refund_body(order.id, amount=2000))
    response = client.post("/refunds", json=refund_body(order.id, amount=1000))
    assert response.status_code == 409
    assert response.json()["code"] == "idempotency_conflict"


def test_ineligible_refund_returns_422_with_reason_code(
    session: Session, client: TestClient
) -> None:
    order = delivered_order(session)
    client.post("/refunds", json=refund_body(order.id))
    response = client.post("/refunds", json=refund_body(order.id, amount=100, key="k2"))
    assert response.status_code == 422
    assert response.json()["code"] == "already_refunded"


def test_refund_amount_above_maximum_returns_422(session: Session, client: TestClient) -> None:
    order = delivered_order(session)
    response = client.post("/refunds", json=refund_body(order.id, amount=9999))
    assert response.status_code == 422
    assert response.json()["code"] == "invalid_request"


def test_invalid_payload_is_rejected_by_validation(client: TestClient) -> None:
    body = refund_body(1, amount=-5)
    assert client.post("/refunds", json=body).status_code == 422


def test_large_refund_waits_for_approval_then_can_be_approved(
    session: Session, client: TestClient
) -> None:
    order = delivered_order(session, price=30000)
    created = client.post("/refunds", json=refund_body(order.id, amount=30000)).json()
    assert created["status"] == "pending_approval"
    approved = client.post(f"/refunds/{created['id']}/approve").json()
    assert approved["status"] == "processed"
    assert client.post(f"/refunds/{created['id']}/reject").status_code == 422


def test_large_refund_can_be_rejected(session: Session, client: TestClient) -> None:
    order = delivered_order(session, price=30000)
    created = client.post("/refunds", json=refund_body(order.id, amount=30000)).json()
    rejected = client.post(f"/refunds/{created['id']}/reject").json()
    assert rejected["status"] == "rejected"


def test_cancel_subscription_endpoint(session: Session, client: TestClient) -> None:
    sub = make_subscription(session, make_customer(session))
    first = client.post(f"/subscriptions/{sub.id}/cancel")
    second = client.post(f"/subscriptions/{sub.id}/cancel")
    assert first.status_code == second.status_code == 200
    assert first.json()["cancel_at_period_end"] is True
    assert client.post("/subscriptions/999/cancel").status_code == 404
