from collections.abc import AsyncIterator, Iterator, Sequence
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from parley.backend.schemas import (
    CustomerOut,
    EligibilityOut,
    InvoiceOut,
    OrderOut,
    RefundOut,
    RefundRequest,
    ShipmentOut,
    SubscriptionOut,
)
from parley.backend.services import (
    Backend,
    IdempotencyConflictError,
    InvalidRequestError,
    NotEligibleError,
    NotFoundError,
)
from parley.clock import utcnow
from parley.db.models import Customer, Invoice, Order, Refund, Shipment, Subscription
from parley.db.session import make_engine


def get_backend(request: Request) -> Iterator[Backend]:
    with Session(request.app.state.engine, expire_on_commit=False) as session:
        yield Backend(session, utcnow)


BackendDep = Annotated[Backend, Depends(get_backend)]


def create_app(engine: Engine | None = None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        app.state.engine = engine or make_engine()
        yield
        app.state.engine.dispose()

    app = FastAPI(title="Parley backend", version="0.1.0", lifespan=lifespan)
    _register_errors(app)
    _register_read_routes(app)
    _register_write_routes(app)
    return app


def _register_errors(app: FastAPI) -> None:
    @app.exception_handler(NotFoundError)
    async def not_found(_: Request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse({"code": "not_found", "detail": str(exc)}, status_code=404)

    @app.exception_handler(NotEligibleError)
    async def not_eligible(_: Request, exc: NotEligibleError) -> JSONResponse:
        return JSONResponse({"code": exc.code, "detail": "not eligible"}, status_code=422)

    @app.exception_handler(InvalidRequestError)
    async def invalid(_: Request, exc: InvalidRequestError) -> JSONResponse:
        return JSONResponse({"code": "invalid_request", "detail": str(exc)}, status_code=422)

    @app.exception_handler(IdempotencyConflictError)
    async def conflict(_: Request, exc: IdempotencyConflictError) -> JSONResponse:
        return JSONResponse({"code": "idempotency_conflict", "detail": str(exc)}, status_code=409)


def _register_read_routes(app: FastAPI) -> None:
    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/customers/lookup", response_model=CustomerOut)
    def lookup_customer(email: str, backend: BackendDep) -> Customer:
        return backend.find_customer_by_email(email)

    @app.get("/customers/{customer_id}", response_model=CustomerOut)
    def get_customer(customer_id: int, backend: BackendDep) -> Customer:
        return backend.get_customer(customer_id)

    @app.get("/customers/{customer_id}/orders", response_model=list[OrderOut])
    def list_orders(customer_id: int, backend: BackendDep) -> Sequence[Order]:
        return backend.list_orders(customer_id)

    @app.get("/customers/{customer_id}/subscriptions", response_model=list[SubscriptionOut])
    def list_subscriptions(customer_id: int, backend: BackendDep) -> Sequence[Subscription]:
        return backend.list_subscriptions(customer_id)

    @app.get("/customers/{customer_id}/invoices", response_model=list[InvoiceOut])
    def list_invoices(customer_id: int, backend: BackendDep) -> Sequence[Invoice]:
        return backend.list_invoices(customer_id)

    @app.get("/orders/{order_id}", response_model=OrderOut)
    def get_order(order_id: int, backend: BackendDep) -> Order:
        return backend.get_order(order_id)

    @app.get("/orders/{order_id}/refund-eligibility", response_model=EligibilityOut)
    def order_eligibility(order_id: int, backend: BackendDep) -> EligibilityOut:
        return EligibilityOut.of(backend.check_order_refund(order_id))

    @app.get("/shipments/{tracking_number}", response_model=ShipmentOut)
    def get_shipment(tracking_number: str, backend: BackendDep) -> Shipment:
        return backend.get_shipment_by_tracking(tracking_number)

    @app.get("/subscriptions/{subscription_id}", response_model=SubscriptionOut)
    def get_subscription(subscription_id: int, backend: BackendDep) -> Subscription:
        return backend.get_subscription(subscription_id)

    @app.get("/invoices/{invoice_id}", response_model=InvoiceOut)
    def get_invoice(invoice_id: int, backend: BackendDep) -> Invoice:
        return backend.get_invoice(invoice_id)

    @app.get("/invoices/{invoice_id}/refund-eligibility", response_model=EligibilityOut)
    def invoice_eligibility(invoice_id: int, backend: BackendDep) -> EligibilityOut:
        return EligibilityOut.of(backend.check_invoice_refund(invoice_id))


def _register_write_routes(app: FastAPI) -> None:
    @app.post("/refunds", response_model=RefundOut, status_code=201)
    def issue_refund(body: RefundRequest, response: Response, backend: BackendDep) -> Refund:
        refund, created = backend.issue_refund(
            body.target, body.target_id, body.amount_cents, body.reason, body.idempotency_key
        )
        backend.session.commit()
        if not created:
            response.status_code = 200
        return refund

    @app.post("/refunds/{refund_id}/approve", response_model=RefundOut)
    def approve_refund(refund_id: int, backend: BackendDep) -> Refund:
        refund = backend.resolve_refund(refund_id, approve=True)
        backend.session.commit()
        return refund

    @app.post("/refunds/{refund_id}/reject", response_model=RefundOut)
    def reject_refund(refund_id: int, backend: BackendDep) -> Refund:
        refund = backend.resolve_refund(refund_id, approve=False)
        backend.session.commit()
        return refund

    @app.post("/subscriptions/{subscription_id}/cancel", response_model=SubscriptionOut)
    def cancel_subscription(subscription_id: int, backend: BackendDep) -> Subscription:
        sub = backend.cancel_subscription(subscription_id)
        backend.session.commit()
        return sub
