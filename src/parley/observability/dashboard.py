import argparse
import html
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from parley.evals.report import percentile
from parley.observability.exporters import read_spans
from parley.settings import PROJECT_ROOT

Span = dict[str, Any]


@dataclass
class Group:
    calls: int = 0
    prompt: int = 0
    completion: int = 0
    cached: int = 0
    cost: float = 0.0
    millis: list[float] = field(default_factory=list)

    def add(self, span: Span) -> None:
        attrs = span["attributes"]
        self.calls += 1
        self.prompt += int(attrs.get("prompt_tokens", 0))
        self.completion += int(attrs.get("completion_tokens", 0))
        self.cached += int(attrs.get("cached_tokens", 0))
        self.cost += float(attrs.get("cost_usd", 0.0))
        self.millis.append(float(span["duration_ms"]))

    @property
    def cache_rate(self) -> float:
        return self.cached / self.prompt if self.prompt else 0.0


def _ancestors(span: Span, by_id: dict[str, Span]) -> list[Span]:
    chain, parent = [], by_id.get(span["parent_id"] or "")
    while parent is not None:
        chain.append(parent)
        parent = by_id.get(parent["parent_id"] or "")
    return chain


def role_of(span: Span, by_id: dict[str, Span]) -> str:
    """The pipeline step a model call belongs to, read from the nearest node span above it."""
    for ancestor in _ancestors(span, by_id):
        if ancestor["name"].startswith("node."):
            return ancestor["name"].removeprefix("node.")
    return "agent"


def category_of(span: Span, by_id: dict[str, Span]) -> str:
    for ancestor in _ancestors(span, by_id):
        if ancestor["kind"] == "scenario":
            return str(ancestor["attributes"].get("category", "unknown"))
    return "unknown"


def group_llm(spans: list[Span], key: str) -> dict[str, Group]:
    """Model calls grouped by `role`, `model`, or `category`."""
    by_id = {s["span_id"]: s for s in spans}
    groups: dict[str, Group] = {}
    for s in spans:
        if s["kind"] != "llm":
            continue
        name = {
            "role": role_of(s, by_id),
            "model": str(s["attributes"].get("model", "unknown")),
            "category": category_of(s, by_id),
        }[key]
        groups.setdefault(name, Group()).add(s)
    return dict(sorted(groups.items(), key=lambda item: -item[1].cost))


def group_tools(spans: list[Span]) -> dict[str, Group]:
    groups: dict[str, Group] = {}
    for s in spans:
        if s["kind"] == "tool":
            groups.setdefault(str(s["attributes"].get("tool", s["name"])), Group()).add(s)
    return dict(sorted(groups.items(), key=lambda item: -item[1].calls))


def node_durations(spans: list[Span]) -> dict[str, list[float]]:
    result: dict[str, list[float]] = {}
    for s in spans:
        if s["kind"] == "node":
            result.setdefault(s["name"].removeprefix("node."), []).append(float(s["duration_ms"]))
    return result


def scenario_spans(spans: list[Span]) -> list[Span]:
    return [s for s in spans if s["kind"] == "scenario"]


def ticket_costs(spans: list[Span]) -> list[float]:
    return [float(s["attributes"].get("cost_usd", 0.0)) for s in scenario_spans(spans)]


def _p50_p95(group: Group) -> str:
    p50, p95 = percentile(group.millis, 0.5), percentile(group.millis, 0.95)
    return f"{p50 / 1000:.1f}s / {p95 / 1000:.1f}s"


def render_cost_table(spans: list[Span]) -> str:
    """Where the money goes, one row per pipeline step, as a Markdown table."""
    roles = group_llm(spans, "role")
    total = sum(g.cost for g in roles.values()) or 1.0
    lines = [
        "| Step | Model calls | Prompt tokens | Completion tokens | Cached | Cost | Share "
        "| p50 / p95 per call |",
        "| --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, g in roles.items():
        lines.append(
            f"| {name} | {g.calls} | {g.prompt} | {g.completion} | {g.cache_rate:.0%} "
            f"| ${g.cost:.4f} | {g.cost / total:.0%} "
            f"| {_p50_p95(g)} |"
        )
    return "\n".join(lines) + "\n"


STYLE = """
body{font:14px/1.5 system-ui,sans-serif;margin:2rem auto;max-width:960px;padding:0 1rem;
color:#1f2328;background:#fff}
@media(prefers-color-scheme:dark){body{color:#e6edf3;background:#0d1117}
th,td{border-color:#30363d}.bar{background:#58a6ff}}
h1{font-size:1.4rem}h2{font-size:1.1rem;margin-top:2rem}
table{border-collapse:collapse;width:100%}
th,td{padding:.35rem .6rem;border-bottom:1px solid #d0d7de;text-align:right}
th:first-child,td:first-child{text-align:left}
.bar{display:inline-block;height:.7rem;background:#0969da;border-radius:2px;vertical-align:middle}
.note{color:#656d76;font-size:.85rem}
"""


def _row(cells: list[str]) -> str:
    return "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"


def _table(head: list[str], rows: list[list[str]]) -> str:
    header = "".join(f"<th>{html.escape(h)}</th>" for h in head)
    return f"<table><tr>{header}</tr>{''.join(_row(r) for r in rows)}</table>"


def _bar(fraction: float) -> str:
    return f'<span class="bar" style="width:{max(1.0, fraction * 160):.0f}px"></span>'


def _group_table(groups: dict[str, Group], first: str) -> str:
    total = sum(g.cost for g in groups.values()) or 1.0
    rows = [
        [
            html.escape(name),
            str(g.calls),
            f"{g.prompt:,}",
            f"{g.completion:,}",
            f"{g.cache_rate:.0%}",
            f"${g.cost:.4f}",
            f"{_bar(g.cost / total)} {g.cost / total:.0%}",
            _p50_p95(g),
        ]
        for name, g in groups.items()
    ]
    head = [
        first,
        "Calls",
        "Prompt tokens",
        "Completion tokens",
        "Cached",
        "Cost",
        "Share",
        "p50 / p95",
    ]
    return _table(head, rows)


def render_dashboard(spans: list[Span], title: str = "Cost and latency") -> str:
    costs = ticket_costs(spans)
    llm_total = sum(g.cost for g in group_llm(spans, "role").values())
    tickets = len(costs) or 1
    summary = (
        f"{len(costs)} tickets, {sum(g.calls for g in group_llm(spans, 'role').values())} model "
        f"calls, ${llm_total:.4f} in model cost, ${llm_total / tickets:.4f} per ticket "
        f"(p50 ${percentile(costs, 0.5):.4f}, p95 ${percentile(costs, 0.95):.4f})."
    )
    nodes = node_durations(spans)
    node_rows = [
        [
            html.escape(name),
            str(len(values)),
            f"{percentile(values, 0.5) / 1000:.2f}s",
            f"{percentile(values, 0.95) / 1000:.2f}s",
        ]
        for name, values in sorted(nodes.items(), key=lambda kv: -sum(kv[1]))
    ]
    tool_rows = [
        [html.escape(name), str(g.calls), f"{percentile(g.millis, 0.5):.1f} ms"]
        for name, g in group_tools(spans).items()
    ]
    sections = [
        f"<h1>{html.escape(title)}</h1>",
        f'<p class="note">{html.escape(summary)}</p>',
        "<h2>Model cost by pipeline step</h2>",
        _group_table(group_llm(spans, "role"), "Step"),
        "<h2>Model cost by model</h2>",
        _group_table(group_llm(spans, "model"), "Model"),
        "<h2>Model cost by ticket category</h2>",
        _group_table(group_llm(spans, "category"), "Category"),
    ]
    if node_rows:
        sections += [
            "<h2>Time per graph node</h2>",
            _table(["Node", "Runs", "p50", "p95"], node_rows),
        ]
    if tool_rows:
        sections += ["<h2>Tool calls</h2>", _table(["Tool", "Calls", "p50"], tool_rows)]
    body = "\n".join(sections)
    return (
        f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
        f'<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{html.escape(title)}</title><style>{STYLE}</style></head><body>{body}</body></html>"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the cost dashboard from a span file.")
    parser.add_argument("traces", type=Path, help="a reports/traces/*.jsonl file")
    parser.add_argument("--out", type=Path, default=PROJECT_ROOT / "reports" / "dashboard.html")
    parser.add_argument("--title", default="Cost and latency")
    args = parser.parse_args()
    spans = read_spans(args.traces)
    if not spans:
        raise SystemExit(f"no spans in {args.traces}")
    args.out.write_text(render_dashboard(spans, args.title), encoding="utf-8")
    print(render_cost_table(spans))


if __name__ == "__main__":
    main()
