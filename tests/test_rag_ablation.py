import pytest
from sqlalchemy.orm import Session

from parley.policies.loader import load_policies
from parley.rag.ablation import (
    NO_EMBEDDER,
    CachedReranker,
    Row,
    best_row,
    measure_filter_effect,
    render_report,
    run_ablation,
)
from parley.rag.chunking import ChunkStrategy
from parley.rag.embedders import HashEmbedder
from parley.rag.evaluation import Metrics, load_questions
from parley.rag.rerankers import OverlapReranker
from parley.rag.retrieval import Mode

EMBEDDERS = {"hash-256": HashEmbedder(256), "hash-128": HashEmbedder(128)}


def metrics(recall_3: float, mrr: float, stale: float = 0.0, n: int = 10) -> Metrics:
    return Metrics(
        n=n,
        recall_at_1=recall_3 / 2,
        recall_at_3=recall_3,
        recall_at_5=recall_3,
        mrr=mrr,
        stale_rate=stale,
    )


def row(name: str, dev: Metrics, test: Metrics | None = None) -> Row:
    return Row(
        strategy=ChunkStrategy.SECTION,
        embedding=name,
        mode=Mode.HYBRID,
        rerank=False,
        dev=dev,
        test=test or dev,
    )


class CountingReranker:
    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def score(self, query: str, texts: list[str]) -> list[float]:
        self.calls.append(texts)
        return [float(len(t)) for t in texts]


def test_cached_reranker_scores_each_pair_once() -> None:
    inner = CountingReranker()
    cached = CachedReranker(inner)
    assert cached.score("q", ["aa", "b"]) == [2.0, 1.0]
    assert cached.score("q", ["b", "aa", "ccc"]) == [1.0, 2.0, 3.0]
    assert inner.calls == [["aa", "b"], ["ccc"]]


def test_best_row_uses_recall_then_mrr_then_stale_rate() -> None:
    low = row("low", metrics(0.5, 0.9))
    high = row("high", metrics(0.8, 0.4))
    tie_worse_mrr = row("tie-a", metrics(0.8, 0.3))
    tie_stale = row("tie-b", metrics(0.8, 0.4, stale=0.2))
    assert best_row([low, tie_worse_mrr, high]).embedding == "high"
    assert best_row([tie_stale, high]).embedding == "high"


def test_best_row_ignores_the_test_split() -> None:
    chosen = row("dev-winner", metrics(0.9, 0.9), test=metrics(0.1, 0.1))
    other = row("other", metrics(0.5, 0.5), test=metrics(1.0, 1.0))
    assert best_row([other, chosen]).embedding == "dev-winner"


@pytest.fixture(scope="module")
def questions():
    return load_questions()


def test_ablation_covers_the_grid_and_dedupes_bm25(session: Session, questions) -> None:
    rows = run_ablation(session, load_policies(), questions, EMBEDDERS, OverlapReranker())
    strategies = len(ChunkStrategy)
    assert len(rows) == strategies * 2 * (1 + 2 * 2)
    bm25 = [r for r in rows if r.mode == Mode.BM25]
    assert len(bm25) == strategies * 2
    assert {r.embedding for r in bm25} == {NO_EMBEDDER}
    assert all(r.dev.n + r.test.n == len(questions) for r in rows)


def test_report_and_filter_effect_for_the_chosen_row(session: Session, questions) -> None:
    docs = load_policies()
    reranker = OverlapReranker()
    rows = run_ablation(session, docs, questions, EMBEDDERS, reranker)
    best = best_row(rows)
    effect = measure_filter_effect(session, docs, questions, best, EMBEDDERS, reranker)
    assert effect.with_filter.stale_rate == 0.0
    assert effect.without_filter.stale_rate > 0.0

    sizes = {"dev": 70, "test": 30, "section": 104}
    report = render_report(rows, best, effect, sizes)
    for heading in (
        "# RAG ablation",
        "## Chosen configuration",
        "## Effect of the metadata filter",
    ):
        assert heading in report
    assert best.label in report
    assert report.count("\n| ") >= len(rows)
