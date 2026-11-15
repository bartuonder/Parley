import json
from pathlib import Path
from typing import Any

import pytest

from parley.observability.dashboard import (
    group_llm,
    group_tools,
    main,
    node_durations,
    render_cost_table,
    render_dashboard,
    role_of,
    ticket_costs,
)

Span = dict[str, Any]


def make(
    span_id: str,
    parent: str | None,
    name: str,
    kind: str,
    ms: float = 100.0,
    **attributes: Any,
) -> Span:
    return {
        "trace_id": "t1",
        "span_id": span_id,
        "parent_id": parent,
        "name": name,
        "kind": kind,
        "started_at": "2026-01-01T00:00:00+00:00",
        "duration_ms": ms,
        "status": "ok",
        "attributes": attributes,
        "events": [],
    }


def llm(span_id: str, parent: str, cost: float, prompt: int, cached: int = 0, **extra: Any) -> Span:
    return make(
        span_id,
        parent,
        "llm.complete",
        "llm",
        prompt_tokens=prompt,
        completion_tokens=20,
        cached_tokens=cached,
        cost_usd=cost,
        model=extra.get("model", "gpt-4.1-mini"),
    )


SPANS = [
    make("s", None, "scenario", "scenario", cost_usd=0.0050, category="refund"),
    make("n1", "s", "node.triage", "node", ms=800),
    llm("l1", "n1", 0.0002, 300, model="gpt-4o-mini"),
    make("n2", "s", "node.investigate", "node", ms=4000),
    llm("l2", "n2", 0.0030, 1500, cached=1024),
    llm("l3", "n2", 0.0010, 1700, cached=1536),
    make("t1", "n2", "tool.get_order", "tool", ms=12, tool="get_order", ok=True),
    make("n3", "s", "node.critic", "node", ms=1500),
    llm("l4", "n3", 0.0008, 900),
    make("s2", None, "scenario", "scenario", cost_usd=0.0020, category="billing"),
    make("n4", "s2", "node.investigate", "node", ms=2000),
    llm("l5", "n4", 0.0020, 1200),
]


def test_a_model_call_belongs_to_the_node_that_contains_it() -> None:
    by_id = {s["span_id"]: s for s in SPANS}
    assert role_of(by_id["l1"], by_id) == "triage" and role_of(by_id["l4"], by_id) == "critic"
    assert role_of(make("x", None, "llm.complete", "llm"), by_id) == "agent"


def test_cost_is_grouped_by_step_model_and_category_and_sorted_by_cost() -> None:
    roles = group_llm(SPANS, "role")
    assert list(roles) == ["investigate", "critic", "triage"]
    assert roles["investigate"].calls == 3 and roles["investigate"].cost == 0.0060
    assert roles["investigate"].cache_rate == 2560 / 4400
    assert set(group_llm(SPANS, "model")) == {"gpt-4.1-mini", "gpt-4o-mini"}
    categories = group_llm(SPANS, "category")
    assert categories["refund"].calls == 4 and categories["billing"].calls == 1


def test_tools_nodes_and_ticket_costs_are_summarized() -> None:
    assert group_tools(SPANS)["get_order"].calls == 1
    assert node_durations(SPANS)["investigate"] == [4000.0, 2000.0]
    assert ticket_costs(SPANS) == [0.005, 0.002]


def test_the_cost_table_shows_each_steps_share() -> None:
    table = render_cost_table(SPANS)
    assert "| investigate | 4 |" in table or "| investigate | 3 |" in table
    assert table.count("\n") == 5 and "| Step | Model calls |" in table
    assert "| triage | 1 |" in table


def test_the_dashboard_is_one_self_contained_page(tmp_path: Path) -> None:
    page = render_dashboard(SPANS, "Multi-agent <core>")
    assert page.startswith("<!doctype html>") and "<style>" in page
    assert "Multi-agent &lt;core&gt;" in page and "<core>" not in page
    for heading in ("Model cost by pipeline step", "Model cost by model", "Time per graph node"):
        assert heading in page
    assert "Tool calls" in page and "get_order" in page
    assert "2 tickets, 5 model calls" in page
    assert "http://" not in page and "https://" not in page


def test_the_command_combines_several_span_files_into_one_page(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    first, second = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    for path, part in ((first, SPANS[:5]), (second, SPANS[5:])):
        path.write_text("".join(json.dumps(s) + chr(10) for s in part), encoding="utf-8")
    out = tmp_path / "page.html"
    monkeypatch.setattr("sys.argv", ["dashboard", str(first), str(second), "--out", str(out)])
    main()
    assert "| investigate |" in capsys.readouterr().out
    assert "Model cost by pipeline step" in out.read_text(encoding="utf-8")
    monkeypatch.setattr("sys.argv", ["dashboard", str(tmp_path / "none.jsonl")])
    with pytest.raises(SystemExit, match="no spans"):
        main()
