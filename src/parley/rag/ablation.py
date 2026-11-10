import argparse
import json
from collections import defaultdict
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy.orm import Session

from parley.db.session import make_engine, session_scope
from parley.policies.loader import load_policies
from parley.policies.models import PolicyDoc
from parley.rag.chunking import ChunkStrategy, chunk_corpus
from parley.rag.embedders import MODEL_REGISTRY, Embedder, HashEmbedder, get_embedder
from parley.rag.evaluation import Metrics, Question, evaluate, load_questions
from parley.rag.indexing import build_index
from parley.rag.rerankers import CrossEncoderReranker, OverlapReranker, Reranker
from parley.rag.retrieval import Mode, Retriever

ROOT = Path(__file__).resolve().parents[3]
REPORT_PATH = ROOT / "docs" / "RAG_ABLATION.md"
JSON_PATH = ROOT / "reports" / "rag_ablation.json"
NO_EMBEDDER = "-"


class Row(BaseModel):
    strategy: ChunkStrategy
    embedding: str
    mode: Mode
    rerank: bool
    dev: Metrics
    test: Metrics

    @property
    def label(self) -> str:
        reranker = "rerank" if self.rerank else "no rerank"
        return f"{self.strategy.value} / {self.embedding} / {self.mode.value} / {reranker}"


class FilterEffect(BaseModel):
    with_filter: Metrics
    without_filter: Metrics


class CachedReranker:
    """Pair scores do not depend on the retriever, so reuse them across configurations."""

    def __init__(self, inner: Reranker) -> None:
        self._inner = inner
        self._cache: dict[tuple[str, str], float] = {}

    def score(self, query: str, texts: list[str]) -> list[float]:
        missing = [t for t in dict.fromkeys(texts) if (query, t) not in self._cache]
        if missing:
            for text, score in zip(missing, self._inner.score(query, missing), strict=True):
                self._cache[(query, text)] = score
        return [self._cache[(query, t)] for t in texts]


def run_ablation(
    session: Session,
    docs: list[PolicyDoc],
    questions: list[Question],
    embedders: dict[str, Embedder],
    reranker: Reranker,
) -> list[Row]:
    dev = [q for q in questions if q.split == "dev"]
    test = [q for q in questions if q.split == "test"]
    cached = CachedReranker(reranker)
    rows: list[Row] = []
    for strategy in ChunkStrategy:
        build_index(session, docs, strategy, list(embedders.values()))
        for position, (name, embedder) in enumerate(embedders.items()):
            retriever = Retriever(session, strategy, embedder, cached)
            for mode in Mode:
                if mode == Mode.BM25 and position > 0:
                    continue
                label = NO_EMBEDDER if mode == Mode.BM25 else name
                for rerank in (False, True):
                    kwargs = {"mode": mode, "rerank": rerank}
                    rows.append(
                        Row(
                            strategy=strategy,
                            embedding=label,
                            mode=mode,
                            rerank=rerank,
                            dev=evaluate(retriever, dev, **kwargs),
                            test=evaluate(retriever, test, **kwargs),
                        )
                    )
    return rows


def best_row(rows: list[Row]) -> Row:
    """Pick on the dev split only: recall@3, then MRR, then fewer stale hits."""
    return max(rows, key=lambda r: (r.dev.recall_at_3, r.dev.mrr, -r.dev.stale_rate))


def measure_filter_effect(
    session: Session,
    docs: list[PolicyDoc],
    questions: list[Question],
    row: Row,
    embedders: dict[str, Embedder],
    reranker: Reranker,
) -> FilterEffect:
    embedder = embedders.get(row.embedding) or next(iter(embedders.values()))
    build_index(session, docs, row.strategy, [embedder])
    retriever = Retriever(session, row.strategy, embedder, reranker)
    test = [q for q in questions if q.split == "test"]
    kwargs = {"mode": row.mode, "rerank": row.rerank}
    return FilterEffect(
        with_filter=evaluate(retriever, test, **kwargs),
        without_filter=evaluate(retriever, test, use_filter=False, **kwargs),
    )


def _cells(m: Metrics) -> str:
    return f"{m.recall_at_1:.2f} | {m.recall_at_3:.2f} | {m.recall_at_5:.2f} | {m.mrr:.2f}"


def _factor_means(rows: list[Row]) -> dict[str, dict[str, tuple[float, float]]]:
    groups: dict[str, dict[str, list[Row]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        groups["chunking"][r.strategy.value].append(r)
        groups["embedding"][r.embedding].append(r)
        groups["mode"][r.mode.value].append(r)
        groups["reranker"]["on" if r.rerank else "off"].append(r)
    return {
        factor: {
            level: (
                sum(r.dev.recall_at_3 for r in members) / len(members),
                sum(r.dev.mrr for r in members) / len(members),
            )
            for level, members in levels.items()
        }
        for factor, levels in groups.items()
    }


def render_report(rows: list[Row], best: Row, effect: FilterEffect, sizes: dict[str, int]) -> str:
    lines = [
        "# RAG ablation",
        "",
        "Generated by `make rag-eval`. Configurations are ranked on the dev split only; the test "
        "split is reported for the chosen one.",
        "",
        f"Questions: {sizes['dev']} dev, {sizes['test']} test. "
        + ", ".join(f"{k} chunks: {v}" for k, v in sizes.items() if k not in ("dev", "test")),
        "",
        "## Chosen configuration",
        "",
        f"**{best.label}**",
        "",
        "| Split | n | R@1 | R@3 | R@5 | MRR | Stale@5 |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for name, m in (("dev", best.dev), ("test", best.test)):
        lines.append(f"| {name} | {m.n} | {_cells(m)} | {m.stale_rate:.2f} |")

    lines += [
        "",
        "## Effect of the metadata filter (chosen configuration, test split)",
        "",
        "| Filter | R@1 | R@3 | R@5 | MRR | Stale@5 |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for name, m in (("as-of + region", effect.with_filter), ("none", effect.without_filter)):
        lines.append(f"| {name} | {_cells(m)} | {m.stale_rate:.2f} |")

    lines += [
        "",
        "## Mean dev score by factor",
        "",
        "| Factor | Level | R@3 | MRR |",
        "| --- | --- | --- | --- |",
    ]
    for factor, levels in _factor_means(rows).items():
        for level, (recall, mrr) in sorted(levels.items(), key=lambda kv: -kv[1][0]):
            lines.append(f"| {factor} | {level} | {recall:.3f} | {mrr:.3f} |")

    lines += [
        "",
        "## All configurations",
        "",
        "| Chunking | Embedding | Mode | Rerank | dev R@1 | dev R@3 | dev R@5 | dev MRR "
        "| test R@3 | test MRR |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    ordered = sorted(rows, key=lambda r: (-r.dev.recall_at_3, -r.dev.mrr))
    for r in ordered:
        lines.append(
            f"| {r.strategy.value} | {r.embedding} | {r.mode.value} | "
            f"{'yes' if r.rerank else 'no'} | {_cells(r.dev)} | "
            f"{r.test.recall_at_3:.2f} | {r.test.mrr:.2f} |"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the RAG ablation and write the report.")
    parser.add_argument("--offline", action="store_true", help="use hash embedders, no downloads")
    args = parser.parse_args()

    docs = load_policies()
    questions = load_questions()
    embedders: dict[str, Embedder]
    reranker: Reranker
    if args.offline:
        embedders = {"hash-256": HashEmbedder(256), "hash-128": HashEmbedder(128)}
        reranker = OverlapReranker()
    else:
        embedders = {alias: get_embedder(alias) for alias in MODEL_REGISTRY}
        reranker = CrossEncoderReranker()

    with session_scope(make_engine()) as session:
        rows = run_ablation(session, docs, questions, embedders, reranker)
        best = best_row(rows)
        effect = measure_filter_effect(session, docs, questions, best, embedders, reranker)

    sizes = {
        "dev": sum(q.split == "dev" for q in questions),
        "test": sum(q.split == "test" for q in questions),
        **{s.value: len(chunk_corpus(docs, s)) for s in ChunkStrategy},
    }
    REPORT_PATH.write_text(render_report(rows, best, effect, sizes), encoding="utf-8")
    JSON_PATH.parent.mkdir(exist_ok=True)
    JSON_PATH.write_text(
        json.dumps([r.model_dump(mode="json") for r in rows], indent=2), encoding="utf-8"
    )
    print(f"best on dev: {best.label}")
    print(f"wrote {REPORT_PATH.relative_to(ROOT)} and {JSON_PATH.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
