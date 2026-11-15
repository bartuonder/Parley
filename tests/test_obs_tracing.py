import asyncio
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from parley.agent.llm import LLMResponse, Usage
from parley.observability.exporters import (
    JsonlExporter,
    PostgresExporter,
    read_spans,
    span_record,
)
from parley.observability.llm import TracedLLM
from parley.observability.tables import TraceSpanRow
from parley.observability.tracing import current_trace_id, span, telemetry, traced_node
from tests.fakes import ScriptedLLM


@pytest.fixture
def memory() -> Iterator[InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    telemetry.configure([exporter])
    yield exporter
    telemetry.shutdown()


def test_spans_nest_and_carry_their_attributes(memory: InMemorySpanExporter) -> None:
    with span("ticket", "ticket", scenario="REF-001") as outer:
        outer.event("guard", what="scan")
        with span("llm.complete", "llm", model="m") as inner:
            inner.set(cost_usd=0.002, tags=["a", "b"], skipped=None)
    inner_span, outer_span = memory.get_finished_spans()
    outer_context = outer_span.get_span_context()
    assert inner_span.parent is not None and outer_span.parent is None and outer_context
    assert inner_span.parent.span_id == outer_context.span_id
    record = span_record(inner_span)
    assert record["kind"] == "llm" and record["attributes"] == {
        "model": "m",
        "cost_usd": 0.002,
        "tags": ["a", "b"],
    }
    assert span_record(outer_span)["events"] == [{"name": "guard", "what": "scan"}]


def test_nothing_is_recorded_and_nothing_breaks_when_tracing_is_off() -> None:
    telemetry.shutdown()
    with span("ticket", "ticket") as handle:
        handle.set(x=1)
        handle.event("e")
        assert handle.trace_id is None and current_trace_id() is None


def test_an_error_marks_the_span_and_still_propagates(memory: InMemorySpanExporter) -> None:
    with pytest.raises(ValueError, match="boom"), span("tool.x", "tool"):
        raise ValueError("boom")
    [finished] = memory.get_finished_spans()
    assert span_record(finished)["status"] == "error"


def test_the_trace_id_is_shared_by_a_whole_ticket(memory: InMemorySpanExporter) -> None:
    with span("ticket", "ticket") as handle:
        with span("a", "node"):
            pass
        assert current_trace_id() == handle.trace_id
    contexts = [s.get_span_context() for s in memory.get_finished_spans()]
    ids = {c.trace_id for c in contexts if c is not None}
    assert len(ids) == 1


def test_a_traced_model_call_records_tokens_cost_and_cache_hits(
    memory: InMemorySpanExporter,
) -> None:
    reply = LLMResponse(
        content="hi",
        usage=Usage(prompt_tokens=1200, completion_tokens=30, cached_tokens=1024, cost_usd=0.003),
    )
    result = asyncio.run(TracedLLM(ScriptedLLM([reply])).complete([{"role": "user"}], []))
    assert result is reply
    [finished] = memory.get_finished_spans()
    attrs = span_record(finished)["attributes"]
    assert attrs["prompt_tokens"] == 1200 and attrs["cached_tokens"] == 1024
    assert attrs["cost_usd"] == 0.003 and attrs["tool_calls"] == 0


def test_a_node_decorator_names_the_span_and_keeps_the_result(
    memory: InMemorySpanExporter,
) -> None:
    @traced_node("critic")
    async def node(state: dict[str, int]) -> dict[str, int]:
        return {"n": state["n"] + 1}

    assert asyncio.run(node({"n": 1})) == {"n": 2}
    assert [s.name for s in memory.get_finished_spans()] == ["node.critic"]


def test_the_jsonl_exporter_writes_one_line_per_span(tmp_path: Path) -> None:
    path = tmp_path / "traces" / "run.jsonl"
    telemetry.configure([JsonlExporter(path)])
    with span("ticket", "ticket", scenario="X"), span("llm.complete", "llm", model="m"):
        pass
    telemetry.shutdown()
    rows = read_spans(path)
    assert [r["name"] for r in rows] == ["llm.complete", "ticket"]
    assert rows[0]["parent_id"] == rows[1]["span_id"] and rows[1]["parent_id"] is None
    assert json.loads(path.read_text(encoding="utf-8").splitlines()[0])["kind"] == "llm"
    assert read_spans(tmp_path / "missing.jsonl") == []


def test_the_postgres_exporter_stores_spans_outside_the_callers_transaction(engine: Engine) -> None:
    telemetry.configure([PostgresExporter(engine)])
    with span("ticket", "ticket", scenario="PG-1") as handle:
        trace_id = handle.trace_id
        with span("tool.get_order", "tool", ok=True):
            pass
    telemetry.shutdown()
    with Session(engine) as session:
        rows = list(session.scalars(select(TraceSpanRow).where(TraceSpanRow.trace_id == trace_id)))
        assert sorted(r.name for r in rows) == ["ticket", "tool.get_order"]
        assert {r.kind for r in rows} == {"ticket", "tool"}
        assert next(r for r in rows if r.kind == "tool").attributes["ok"] is True
        for row in rows:
            session.delete(row)
        session.commit()
