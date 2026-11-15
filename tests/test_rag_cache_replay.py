import json
from pathlib import Path

from parley.rag.cache_replay import queries_from_reports, render, replay


def test_policy_questions_are_read_from_the_stored_traces(tmp_path: Path) -> None:
    report = {
        "outcomes": [
            {"trace": [{"name": "search_policies", "arguments": {"query": "return window"}}]},
            {"trace": [{"name": "get_order", "arguments": {"order_id": 1}}]},
            {
                "trace": [
                    {"name": "search_policies", "arguments": {"query": "premium days"}},
                    {"name": "search_policies", "arguments": {}},
                ]
            },
        ]
    }
    path = tmp_path / "r.json"
    path.write_text(json.dumps(report), encoding="utf-8")
    assert queries_from_reports([path, path]) == ["return window", "premium days"] * 2


def embed(text: str) -> list[float]:
    table = {"a": [1.0, 0.0], "a2": [0.99, 0.05], "b": [0.0, 1.0]}
    return table[text]


def test_replay_counts_reuse_and_whether_the_reused_answer_was_right() -> None:
    answers = {"a": ["P1", "P2"], "a2": ["P1", "P3"], "b": ["P9"]}
    rows = replay(["a", "a2", "b", "a"], lambda q: answers[q], embed, [0.9, 0.9999])
    loose, strict = rows
    assert (loose.queries, loose.hits) == (4, 2)
    assert loose.same_top == 2 and loose.same_set == 1
    assert loose.hit_rate == 0.5 and loose.top_agreement == 1.0 and loose.set_agreement == 0.5
    assert strict.hits == 1 and strict.same_set == 1


def test_the_table_lists_each_threshold() -> None:
    rows = replay(["a", "a2"], lambda q: ["P1"], embed, [0.9])
    text = render(rows, fresh_ms=120.0)
    assert "A fresh search takes 120 ms" in text and "| 0.90 | 50% (1) | 100% | 100% |" in text
