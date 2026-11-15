import json
from pathlib import Path
from typing import Any

import pytest

from parley.observability.compare import load, render_table, stats, trace_file


def llm_span(prompt: int, cached: int) -> dict[str, Any]:
    return {"kind": "llm", "attributes": {"prompt_tokens": prompt, "cached_tokens": cached}}


def report(
    success: list[bool], cost: float, latency: float, harm: float | None = None
) -> dict[str, Any]:
    outcomes = [
        {"success": ok, "handover_ok": True, "cost_usd": cost, "latency_s": latency}
        for ok in success
    ]
    return {"outcomes": outcomes, "summary": {"attack_success_rate": harm}}


def test_stats_summarize_outcomes_and_model_calls() -> None:
    spans = [llm_span(1000, 400), llm_span(1000, 600), {"kind": "tool", "attributes": {}}]
    s = stats(report([True, False], 0.004, 5.0), spans)
    assert s.tickets == 2 and s.success == 0.5 and s.cost == pytest.approx(0.004)
    assert s.calls == 1.0 and s.prompt_tokens == 1000 and s.cached_share == 0.5
    assert s.attack_harm is None


def test_the_table_shows_both_sides_and_the_relative_change() -> None:
    before = stats(report([True] * 9 + [False], 0.0040, 8.0), [llm_span(2000, 0)] * 10)
    after = stats(report([True] * 10, 0.0030, 6.0), [llm_span(1500, 750)] * 10)
    text = render_table({"core": (before, after)})
    assert "| core (10 tickets) | Task success | 90.0% | 100.0% | +10.0% |" in text
    assert "| core (10 tickets) | Cost per ticket | $0.0040 | $0.0030 | -25% |" in text
    assert "| Latency p50 | 8.0s | 6.0s | -25% |" in text
    assert "Share of prompt tokens cached | 0% | 50% | +50%" in text
    assert "Attacks that landed" not in text


def test_attack_harm_is_listed_when_both_runs_have_it() -> None:
    before = stats(report([True], 0.004, 5.0, harm=0.1), [])
    after = stats(report([True], 0.004, 5.0, harm=0.0), [])
    assert "| Attacks that landed | 10.0% | 0.0% |" in render_table({"redteam": (before, after)})


def test_a_report_is_loaded_with_the_span_file_next_to_it(tmp_path: Path) -> None:
    path = tmp_path / "run.json"
    path.write_text(json.dumps(report([True], 0.002, 3.0)), encoding="utf-8")
    assert trace_file(path) == tmp_path / "traces" / "run.jsonl"
    spans = tmp_path / "traces"
    spans.mkdir()
    (spans / "run.jsonl").write_text(json.dumps(llm_span(100, 50)) + chr(10), encoding="utf-8")
    assert load(path).cached_share == 0.5
