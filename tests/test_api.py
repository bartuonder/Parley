from collections.abc import Iterator
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from parley.backend.api import create_app, get_backend
from parley.backend.services import Backend
from parley.db.enums import OrderStatus, ShipmentStatus
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


def delivered_order(session: Session, price: int = 5000):
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
