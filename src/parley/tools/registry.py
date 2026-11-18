import json
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError

from parley.backend.services import (
    BackendError,
    IdempotencyConflictError,
    InvalidRequestError,
    NotEligibleError,
    NotFoundError,
)
from parley.observability.tracing import span, telemetry
from parley.security.guards import LOCK_MESSAGE, LOCKED_TOOLS
from parley.security.redact import redact
from parley.tools.access import AccessDeniedError
from parley.tools.context import ToolContext
from parley.tools.permissions import MUTATING, Permission

CONTENT_LIMIT = 4000


class ToolUnavailableError(Exception):
    """The tool exists but its dependency is not configured in this run."""


class ToolParams(BaseModel):
    """Base for tool arguments; unknown fields are an error the model can see and fix."""

    model_config = ConfigDict(extra="forbid")


class ToolResult(BaseModel):
    ok: bool
    data: dict[str, Any] | None = None
    error_code: str | None = None
    message: str | None = None

    @classmethod
    def success(cls, output: BaseModel) -> "ToolResult":
        return cls(ok=True, data=output.model_dump(mode="json"))

    @classmethod
    def failure(cls, code: str, message: str) -> "ToolResult":
        return cls(ok=False, error_code=code, message=message)


@dataclass(frozen=True)
class ToolSpec[P: ToolParams]:
    name: str
    description: str
    permission: Permission
    params: type[P]
    handler: Callable[[ToolContext, P], BaseModel]

    def json_schema(self) -> dict[str, Any]:
        return self.params.model_json_schema()


class ToolRegistry:
    def __init__(self, specs: Sequence[ToolSpec[Any]]) -> None:
        self._specs: dict[str, ToolSpec[Any]] = {}
        for spec in specs:
            if spec.name in self._specs:
                raise ValueError(f"duplicate tool name: {spec.name}")
            self._specs[spec.name] = spec

    @property
    def specs(self) -> list[ToolSpec[Any]]:
        return list(self._specs.values())

    def call(self, ctx: ToolContext, name: str, arguments: dict[str, Any]) -> ToolResult:
        with span(f"tool.{name}", "tool", tool=name) as handle:
            result = self._call(ctx, name, arguments)
            handle.set(ok=result.ok, error_code=result.error_code)
            if telemetry.capture_content:
                handle.set(arguments=_content(arguments), output=_content(result.model_dump()))
            return result

    def _call(self, ctx: ToolContext, name: str, arguments: dict[str, Any]) -> ToolResult:
        spec = self._specs.get(name)
        if spec is None:
            return ToolResult.failure("unknown_tool", f"no tool named {name}")
        if spec.permission not in ctx.allowed:
            return ToolResult.failure("permission_denied", f"{name} needs {spec.permission} access")
        if ctx.write_locked and name in LOCKED_TOOLS:
            return ToolResult.failure("locked", LOCK_MESSAGE)
        try:
            params = spec.params.model_validate(arguments)
        except ValidationError as exc:
            return ToolResult.failure("invalid_arguments", _summarize(exc))
        try:
            return ToolResult.success(_run(ctx, spec, params))
        except AccessDeniedError as exc:
            return ToolResult.failure("access_denied", str(exc))
        except NotFoundError as exc:
            return ToolResult.failure("not_found", str(exc))
        except NotEligibleError as exc:
            return ToolResult.failure("not_eligible", exc.code)
        except ToolUnavailableError as exc:
            return ToolResult.failure("unavailable", str(exc))
        except IdempotencyConflictError as exc:
            return ToolResult.failure("idempotency_conflict", str(exc))
        except (InvalidRequestError, BackendError) as exc:
            return ToolResult.failure("invalid_request", str(exc))


def _run(ctx: ToolContext, spec: ToolSpec[Any], params: ToolParams) -> BaseModel:
    if spec.permission not in MUTATING:
        return spec.handler(ctx, params)
    session = ctx.backend.session
    with session.begin_nested():
        output = spec.handler(ctx, params)
    session.commit()
    return output


def _content(value: Any) -> str:
    """Tool arguments or output for a trace: personal data masked, long text cut."""
    text = redact(json.dumps(value, default=str, separators=(",", ":")))
    return text if len(text) <= CONTENT_LIMIT else text[:CONTENT_LIMIT] + "..."


def _summarize(exc: ValidationError) -> str:
    return "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors())
