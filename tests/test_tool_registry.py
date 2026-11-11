import pytest
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from parley.backend.services import Backend, NotEligibleError, NotFoundError
from parley.db.models import Customer
from parley.tools.access import AccessDeniedError
from parley.tools.context import ToolContext
from parley.tools.permissions import ALL_PERMISSIONS, Permission
from parley.tools.registry import ToolParams, ToolRegistry, ToolSpec
from tests.factories import NOW, make_customer


class Echo(ToolParams):
    text: str = Field(min_length=1)


class Reply(BaseModel):
    text: str


def echo(ctx: ToolContext, params: Echo) -> Reply:
    return Reply(text=params.text)


def raising(error: Exception) -> ToolSpec[Echo]:
    def handler(ctx: ToolContext, params: Echo) -> Reply:
        raise error

    return ToolSpec("boom", "always fails", Permission.READ, Echo, handler)


def create_customer(ctx: ToolContext, params: Echo) -> Reply:
    ctx.backend.session.add(
        Customer(email=params.text, name="New", country="US", tier="standard", created_at=NOW)
    )
    ctx.backend.session.flush()
    if params.text.startswith("fail"):
        raise NotEligibleError("window_expired")
    return Reply(text="created")


def customer_count(session: Session) -> int:
    return session.scalar(select(func.count()).select_from(Customer)) or 0


@pytest.fixture
def ctx(session: Session) -> ToolContext:
    sender = make_customer(session)
    return ToolContext(Backend(session, lambda: NOW), sender.id, "T-1")


def registry(*extra: ToolSpec[Echo]) -> ToolRegistry:
    base = ToolSpec("echo", "repeat the text", Permission.READ, Echo, echo)
    return ToolRegistry([base, *extra])


def test_call_returns_dumped_output(ctx: ToolContext) -> None:
    result = registry().call(ctx, "echo", {"text": "hi"})
    assert result.ok and result.data == {"text": "hi"}


def test_unknown_tool_and_bad_arguments_are_reported(ctx: ToolContext) -> None:
    reg = registry()
    assert reg.call(ctx, "nope", {}).error_code == "unknown_tool"
    bad = reg.call(ctx, "echo", {"text": ""})
    assert bad.error_code == "invalid_arguments" and "text" in (bad.message or "")
    extra = reg.call(ctx, "echo", {"text": "x", "extra": 1})
    assert extra.error_code == "invalid_arguments"


def test_permission_levels_gate_tools(ctx: ToolContext) -> None:
    risky = ToolSpec("pay", "moves money", Permission.RISKY, Echo, echo)
    reg = registry(risky)
    ctx.allowed = frozenset({Permission.READ, Permission.WRITE})
    assert reg.call(ctx, "pay", {"text": "x"}).error_code == "permission_denied"
    assert reg.call(ctx, "echo", {"text": "x"}).ok
    ctx.allowed = ALL_PERMISSIONS
    assert reg.call(ctx, "pay", {"text": "x"}).ok


@pytest.mark.parametrize(
    ("error", "code"),
    [
        (AccessDeniedError("not yours"), "access_denied"),
        (NotFoundError("gone"), "not_found"),
        (NotEligibleError("window_expired"), "not_eligible"),
    ],
)
def test_domain_errors_map_to_codes(ctx: ToolContext, error: Exception, code: str) -> None:
    result = registry(raising(error)).call(ctx, "boom", {"text": "x"})
    assert not result.ok and result.error_code == code


def test_failed_write_rolls_back_only_its_own_changes(session: Session, ctx: ToolContext) -> None:
    write = ToolSpec("create", "adds a customer", Permission.WRITE, Echo, create_customer)
    reg = registry(write)
    before = customer_count(session)
    assert reg.call(ctx, "create", {"text": "ok@example.com"}).ok
    failed = reg.call(ctx, "create", {"text": "fail@example.com"})
    assert failed.error_code == "not_eligible"
    assert customer_count(session) == before + 1
    assert session.get(Customer, ctx.customer_id) is not None


def test_duplicate_tool_names_are_rejected() -> None:
    spec = ToolSpec("echo", "repeat", Permission.READ, Echo, echo)
    with pytest.raises(ValueError, match="duplicate"):
        ToolRegistry([spec, spec])
