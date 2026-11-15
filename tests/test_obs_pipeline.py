import asyncio
from collections.abc import Iterator

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from sqlalchemy.orm import Session

from parley.evals.agent_run import Architecture, LLMFactory, run_scenario
from parley.evals.loader import load_scenarios
from parley.evals.scoring import ScenarioOutcome
from parley.observability.exporters import span_record
from parley.observability.tracing import telemetry
from tests.fakes import reference_llm, reference_multi_llm, router_for

REF_001 = next(s for s in load_scenarios() if s.id == "REF-001")


@pytest.fixture
def spans() -> Iterator[InMemorySpanExporter]:
    exporter = InMemorySpanExporter()
    telemetry.configure([exporter])
    yield exporter
    telemetry.shutdown()


def play(session: Session, llm_for: LLMFactory, arch: Architecture) -> ScenarioOutcome:
    return asyncio.run(
        run_scenario(
            session,
            REF_001,
            llm_for,
            lambda _: None,
            model="m",
            max_steps=8,
            max_cost_usd=1.0,
            arch=arch,
        )
    )


def names(exporter: InMemorySpanExporter) -> list[str]:
    return [s.name for s in exporter.get_finished_spans()]


def test_a_single_agent_ticket_is_one_trace_of_model_and_tool_spans(
    session: Session, spans: InMemorySpanExporter
) -> None:
    outcome = play(session, reference_llm, Architecture())
    recorded = names(spans)
    assert recorded[-2:] == ["ticket", "scenario"]
    assert "llm.complete" in recorded and "tool.issue_refund" in recorded
    records = [span_record(s) for s in spans.get_finished_spans()]
    assert len({r["trace_id"] for r in records}) == 1
    assert outcome.trace_id == records[0]["trace_id"]
    scenario = records[-1]
    assert scenario["attributes"]["scenario_id"] == "REF-001" and scenario["attributes"]["success"]
    assert scenario["attributes"]["cost_usd"] == pytest.approx(outcome.cost_usd)


def test_the_multi_agent_graph_shows_each_node_with_its_calls_inside(
    session: Session, spans: InMemorySpanExporter
) -> None:
    play(session, reference_multi_llm, Architecture(name="multi", router_llm_factory=router_for))
    by_id = {r["span_id"]: r for r in (span_record(s) for s in spans.get_finished_spans())}

    def parent_name(record: dict[str, object]) -> str | None:
        parent = by_id.get(str(record["parent_id"]))
        return str(parent["name"]) if parent else None

    nodes = [n for n in names(spans) if n.startswith("node.")]
    assert nodes == [
        "node.triage",
        "node.investigate",
        "node.critic",
        "node.execute",
        "node.respond",
        "node.remember",
    ]
    llm_parents = [parent_name(r) for r in by_id.values() if r["name"] == "llm.complete"]
    assert llm_parents.count("node.triage") == 1 and llm_parents.count("node.critic") == 1
    assert llm_parents.count("node.respond") == 1 and "node.investigate" in llm_parents
    tool = next(r for r in by_id.values() if r["name"] == "tool.issue_refund")
    assert parent_name(tool) == "node.execute" and tool["attributes"]["ok"] is True


def test_nothing_is_traced_and_the_outcome_has_no_trace_id_when_tracing_is_off(
    session: Session,
) -> None:
    telemetry.shutdown()
    assert play(session, reference_llm, Architecture()).trace_id is None
