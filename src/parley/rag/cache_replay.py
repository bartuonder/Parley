import argparse
import json
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from parley.db.session import make_engine, session_scope
from parley.rag.cache import SemanticCache
from parley.rag.service import build_default_index, default_retriever, search_policies
from parley.seed.config import REFERENCE_NOW

Search = Callable[[str], list[str]]
Embed = Callable[[str], list[float]]


@dataclass(frozen=True)
class ReplayRow:
    threshold: float
    queries: int
    hits: int
    same_top: int
    same_set: int

    @property
    def hit_rate(self) -> float:
        return self.hits / self.queries if self.queries else 0.0

    @property
    def top_agreement(self) -> float:
        return self.same_top / self.hits if self.hits else 1.0

    @property
    def set_agreement(self) -> float:
        return self.same_set / self.hits if self.hits else 1.0


def queries_from_reports(paths: list[Path]) -> list[str]:
    """Policy questions the agent asked, in the order the scenarios ran."""
    queries: list[str] = []
    for path in paths:
        for outcome in json.loads(path.read_text(encoding="utf-8"))["outcomes"]:
            queries += [
                str(t["arguments"]["query"])
                for t in outcome["trace"]
                if t["name"] == "search_policies" and "query" in t["arguments"]
            ]
    return queries


def replay(
    queries: list[str], search: Search, embed: Embed, thresholds: list[float]
) -> list[ReplayRow]:
    """For each threshold: how often a cached answer would be reused, and whether it was right."""
    rows = []
    for threshold in thresholds:
        cache = SemanticCache(threshold, capacity=10_000)
        hits = same_top = same_set = 0
        for query in queries:
            vector = embed(query)
            fresh = search(query)
            cached = cache.get("replay", vector)
            if cached is None:
                cache.put("replay", vector, fresh)
                continue
            hits += 1
            same_top += bool(cached and fresh and cached[0] == fresh[0])
            same_set += set(cached) == set(fresh)
        rows.append(ReplayRow(threshold, len(queries), hits, same_top, same_set))
    return rows


def render(rows: list[ReplayRow], fresh_ms: float) -> str:
    lines = [
        f"Policy questions replayed: {rows[0].queries if rows else 0}. A fresh search takes "
        f"{fresh_ms:.0f} ms.",
        "",
        "| Threshold | Reused | Same best passage | Same five passages |",
        "| --- | --- | --- | --- |",
    ]
    lines += [
        f"| {r.threshold:.2f} | {r.hit_rate:.0%} ({r.hits}) | {r.top_agreement:.0%} "
        f"| {r.set_agreement:.0%} |"
        for r in rows
    ]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay recorded policy questions with a cache.")
    parser.add_argument("reports", nargs="+", type=Path, help="eval report JSON files")
    parser.add_argument("--thresholds", nargs="*", type=float, default=[0.85, 0.9, 0.95])
    args = parser.parse_args()
    queries = queries_from_reports(args.reports)
    if not queries:
        raise SystemExit("no policy questions found in the reports")
    with session_scope(make_engine()) as session:
        build_default_index(session)
        retriever = default_retriever(session)

        def search(query: str) -> list[str]:
            hits = search_policies(retriever, query, as_of=REFERENCE_NOW.date())
            return [h.citation for h in hits]

        started = time.perf_counter()
        for query in queries[:20]:
            search(query)
        fresh_ms = (time.perf_counter() - started) / min(20, len(queries)) * 1000
        rows = replay(queries, search, retriever.embedder.embed_query, args.thresholds)
    print(render(rows, fresh_ms))


if __name__ == "__main__":
    main()
