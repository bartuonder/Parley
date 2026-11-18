import functools
from collections.abc import Callable, Coroutine, Iterator, Sequence
from contextlib import contextmanager
from typing import Any

from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, SpanExporter
from opentelemetry.trace import Span, StatusCode, get_current_span

TRACER_NAME = "parley"
Attributes = dict[str, Any]


class SpanHandle:
    """What the code inside a span sees; a no-op when tracing is not configured."""

    def __init__(self, span: Span | None) -> None:
        self._span = span

    def set(self, **attributes: Any) -> None:
        if self._span is None:
            return
        for key, value in attributes.items():
            if value is not None:
                self._span.set_attribute(key, _plain(value))

    def event(self, name: str, **attributes: Any) -> None:
        if self._span is not None:
            self._span.add_event(name, {k: _plain(v) for k, v in attributes.items()})

    @property
    def trace_id(self) -> str | None:
        if self._span is None:
            return None
        return f"{self._span.get_span_context().trace_id:032x}"


def _plain(value: Any) -> Any:
    if isinstance(value, bool | int | float | str):
        return value
    if isinstance(value, list | tuple):
        return [str(v) for v in value]
    return str(value)


class Telemetry:
    """Process-wide switch for tracing: spans go to the configured exporters or nowhere."""

    def __init__(self) -> None:
        self._provider: TracerProvider | None = None
        self.capture_content = False

    def configure(
        self,
        exporters: Sequence[SpanExporter],
        capture_content: bool = False,
        batch: bool = False,
    ) -> None:
        """Send spans to exporters; `batch` exports from a background thread, off the caller."""
        self.shutdown()
        self.capture_content = capture_content
        provider = TracerProvider()
        for exporter in exporters:
            provider.add_span_processor(
                BatchSpanProcessor(exporter, schedule_delay_millis=500)
                if batch
                else SimpleSpanProcessor(exporter)
            )
        self._provider = provider

    def shutdown(self) -> None:
        if self._provider is not None:
            self._provider.shutdown()
            self._provider = None
        self.capture_content = False

    @property
    def enabled(self) -> bool:
        return self._provider is not None

    @contextmanager
    def span(self, name: str, kind: str, **attributes: Any) -> Iterator[SpanHandle]:
        if self._provider is None:
            yield SpanHandle(None)
            return
        tracer = self._provider.get_tracer(TRACER_NAME)
        with tracer.start_as_current_span(name, record_exception=False) as active:
            active.set_attribute("parley.kind", kind)
            handle = SpanHandle(active)
            handle.set(**attributes)
            try:
                yield handle
            except BaseException as exc:
                active.set_status(StatusCode.ERROR, type(exc).__name__)
                raise


telemetry = Telemetry()


def span(name: str, kind: str, **attributes: Any) -> Any:
    return telemetry.span(name, kind, **attributes)


def current_trace_id() -> str | None:
    context = get_current_span().get_span_context()
    return f"{context.trace_id:032x}" if context.is_valid else None


def traced_node[**P, R](
    name: str,
) -> Callable[[Callable[P, Coroutine[Any, Any, R]]], Callable[P, Coroutine[Any, Any, R]]]:
    """Wrap a graph node in a span named after it, keeping the signature LangGraph reads."""

    def decorate(
        node: Callable[P, Coroutine[Any, Any, R]],
    ) -> Callable[P, Coroutine[Any, Any, R]]:
        @functools.wraps(node)
        async def run(*args: P.args, **kwargs: P.kwargs) -> R:
            with span(f"node.{name}", "node"):
                return await node(*args, **kwargs)

        return run

    return decorate
