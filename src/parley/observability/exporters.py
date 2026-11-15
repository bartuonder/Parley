import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from opentelemetry.sdk.trace import ReadableSpan
from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from parley.observability.tables import TraceSpanRow

KIND_KEY = "parley.kind"


def span_record(span: ReadableSpan) -> dict[str, Any]:
    """One finished span as a plain dictionary, the shape every sink stores."""
    context = span.get_span_context()
    parent = span.parent
    attributes = {
        k: list(v) if isinstance(v, tuple) else v for k, v in (span.attributes or {}).items()
    }
    start, end = span.start_time or 0, span.end_time or 0
    return {
        "trace_id": f"{context.trace_id:032x}" if context else "",
        "span_id": f"{context.span_id:016x}" if context else "",
        "parent_id": f"{parent.span_id:016x}" if parent else None,
        "name": span.name,
        "kind": str(attributes.pop(KIND_KEY, "span")),
        "started_at": datetime.fromtimestamp(start / 1e9, tz=UTC).isoformat(),
        "duration_ms": (end - start) / 1e6,
        "status": span.status.status_code.name.lower(),
        "attributes": attributes,
        "events": [{"name": e.name, **dict(e.attributes or {})} for e in span.events],
    }


class JsonlExporter(SpanExporter):
    """Appends one JSON line per finished span to a file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        with self.path.open("a", encoding="utf-8") as handle:
            for span in spans:
                handle.write(json.dumps(span_record(span)) + "\n")
        return SpanExportResult.SUCCESS


class PostgresExporter(SpanExporter):
    """Stores finished spans in `trace_spans` on its own connection, outside ticket transactions."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        rows = []
        for span in spans:
            record = span_record(span)
            record["started_at"] = datetime.fromisoformat(record["started_at"])
            rows.append(TraceSpanRow(**record))
        with Session(self._engine) as session:
            session.add_all(rows)
            session.commit()
        return SpanExportResult.SUCCESS


def read_spans(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
