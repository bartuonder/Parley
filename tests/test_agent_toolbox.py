import asyncio
from datetime import timedelta

import pytest
from sqlalchemy.orm import Session

from parley.agent.result import ToolInvocation
from parley.agent.toolbox import open_toolbox
from parley.backend.services import Backend
from parley.tools.catalog import default_registry
from parley.tools.context import ToolContext
from tests.factories import NOW, make_customer, make_order

REGISTRY = default_registry()


@pytest.fixture
def ctx(session: Session) -> ToolContext:
    sender = make_customer(session, "ada@example.com")
    return ToolContext(Backend(session, lambda: NOW + timedelta(days=1)), sender.id, "T-1")


def test_schemas_use_the_function_calling_format(ctx: ToolContext) -> None:
    async def run() -> list[dict[str, object]]:
        async with open_toolbox(REGISTRY, ctx) as box:
            return box.schemas

    schemas = asyncio.run(run())
    assert len(schemas) == len(REGISTRY.specs)
    first = schemas[0]
    assert first["type"] == "function"
    function = first["function"]
    assert isinstance(function, dict) and function["name"] and "parameters" in function


def test_call_returns_trace_entry_and_model_text(session: Session, ctx: ToolContext) -> None:
    order = make_order(session, ctx.backend.get_customer(ctx.customer_id))

    async def run() -> tuple[ToolInvocation, str]:
        async with open_toolbox(REGISTRY, ctx) as box:
            return await box.call("get_order", {"order_id": order.id})

    invocation, text = asyncio.run(run())
    assert invocation.ok and invocation.output["id"] == order.id
    assert '"ok":true' in text.replace(" ", "")


def test_failed_call_is_traced_with_its_error_code(session: Session, ctx: ToolContext) -> None:
    other = make_order(session, make_customer(session, "bob@example.com"))

    async def run() -> ToolInvocation:
        async with open_toolbox(REGISTRY, ctx) as box:
            invocation, _ = await box.call("get_order", {"order_id": other.id})
            return invocation

    invocation = asyncio.run(run())
    assert not invocation.ok
    assert invocation.output["error_code"] == "access_denied"


def test_errors_raised_inside_the_toolbox_keep_their_original_type(ctx: ToolContext) -> None:
    async def run() -> None:
        async with open_toolbox(REGISTRY, ctx):
            raise KeyError("boom")

    with pytest.raises(KeyError, match="boom"):
        asyncio.run(run())
