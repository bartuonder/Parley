import asyncio
import json
from datetime import timedelta
from typing import Any

import pytest
from mcp import Client
from sqlalchemy.orm import Session

from parley.agent.toolbox import open_toolbox
from parley.backend.services import Backend
from parley.db.enums import OrderStatus, ShipmentStatus
from parley.db.models import Order
from parley.tools.catalog import default_registry
from parley.tools.context import ToolContext
from parley.tools.server import build_server
from tests.factories import NOW, make_customer, make_item, make_order, make_shipment

REGISTRY = default_registry()


@pytest.fixture
def ctx(session: Session) -> ToolContext:
    sender = make_customer(session, "ada@example.com")
    return ToolContext(Backend(session, lambda: NOW + timedelta(days=10)), sender.id, "T-1")


def delivered_order(session: Session, ctx: ToolContext, price: int = 5000) -> Order:
    order = make_order(session, ctx.backend.get_customer(ctx.customer_id), total_cents=price)
    make_item(session, order, unit_price_cents=price)
    make_shipment(session, order, status=ShipmentStatus.DELIVERED, delivered_at=NOW)
    order.status = OrderStatus.DELIVERED
    session.flush()
    return order


def over_mcp(ctx: ToolContext, name: str, arguments: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    async def run() -> tuple[bool, dict[str, Any]]:
        async with Client(build_server(REGISTRY, ctx)) as client:
            result = await client.call_tool(name, arguments)
            return result.is_error, json.loads(result.content[0].text)  # type: ignore[union-attr]

    return asyncio.run(run())


def test_server_lists_every_registry_tool_with_its_schema(ctx: ToolContext) -> None:
    async def run() -> list[Any]:
        async with Client(build_server(REGISTRY, ctx)) as client:
            return (await client.list_tools()).tools

    tools = asyncio.run(run())
    assert [t.name for t in tools] == [s.name for s in REGISTRY.specs]
    refund = next(t for t in tools if t.name == "issue_refund")
    spec = next(s for s in REGISTRY.specs if s.name == "issue_refund")
    assert refund.input_schema == spec.json_schema()
    assert "amount_cents" in refund.input_schema["properties"]
    read_only = {t.name: t.annotations.read_only_hint for t in tools if t.annotations}
    assert read_only["get_order"] is True and read_only["issue_refund"] is False


def test_mcp_call_matches_a_direct_registry_call(session: Session, ctx: ToolContext) -> None:
    order = delivered_order(session, ctx)
    args = {"order_id": order.id}
    is_error, payload = over_mcp(ctx, "get_order", args)
    direct = REGISTRY.call(ctx, "get_order", args)
    assert not is_error and payload == direct.model_dump(mode="json")


def test_mcp_write_changes_state_and_errors_are_flagged(session: Session, ctx: ToolContext) -> None:
    order = delivered_order(session, ctx)
    refund = {"target": "order", "target_id": order.id, "amount_cents": 5000, "reason": "late"}
    is_error, payload = over_mcp(ctx, "issue_refund", refund)
    assert not is_error and payload["data"]["status"] == "processed"
    assert session.get_one(Order, order.id).status == OrderStatus.REFUNDED
    is_error, payload = over_mcp(ctx, "issue_refund", {**refund, "amount_cents": 1})
    assert is_error and payload["error_code"] == "not_eligible"


def test_mcp_enforces_sender_scoping(session: Session, ctx: ToolContext) -> None:
    other = make_order(session, make_customer(session, "bob@example.com"))
    is_error, payload = over_mcp(ctx, "get_order", {"order_id": other.id})
    assert is_error and payload["error_code"] == "access_denied"


def test_compact_output_leaves_out_empty_fields_and_keeps_the_rest(session: Session) -> None:
    async def fetch(compact: bool) -> str:
        sender = make_customer(session, f"x{compact}@example.com")
        ctx = ToolContext(Backend(session, lambda: NOW), sender.id, "T-1", compact_output=compact)
        async with open_toolbox(default_registry(), ctx) as box:
            _, text = await box.call("get_customer_overview", {})
            return text

    plain = asyncio.run(fetch(False))
    compact = asyncio.run(fetch(True))
    assert '"error_code":null' in plain and '"error_code"' not in compact
    assert len(compact) < len(plain) and '"ok":true' in compact
