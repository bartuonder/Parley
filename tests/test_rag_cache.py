from typing import Any

import pytest
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from parley.observability.exporters import span_record
from parley.observability.tracing import telemetry
from parley.rag.cache import CachedRetriever, SemanticCache, cosine
from parley.rag.embedders import HashEmbedder
from parley.rag.filters import SearchFilter
from parley.rag.retrieval import Retriever


def test_cosine_is_one_for_equal_directions_and_zero_for_orthogonal_ones() -> None:
    assert cosine([1.0, 0.0], [2.0, 0.0]) == pytest.approx(1.0)
    assert cosine([1.0, 0.0], [0.0, 3.0]) == 0.0
    assert cosine([0.0, 0.0], [1.0, 1.0]) == 0.0


def test_a_close_vector_hits_and_a_distant_one_misses() -> None:
    cache = SemanticCache(threshold=0.95)
    cache.put("k", [1.0, 0.0], "answer")
    assert cache.get("k", [0.99, 0.05]) == "answer"
    assert cache.get("k", [0.5, 0.9]) is None
    assert (cache.hits, cache.misses, cache.hit_rate) == (1, 1, 0.5)


def test_the_same_vector_under_another_key_never_hits() -> None:
    cache = SemanticCache()
    cache.put(("2026-06-01", "global"), [1.0, 0.0], "june")
    assert cache.get(("2026-07-01", "global"), [1.0, 0.0]) is None
    assert cache.get(("2026-06-01", "global"), [1.0, 0.0]) == "june"


def test_the_best_match_wins_and_the_oldest_entry_is_dropped_at_capacity() -> None:
    best = SemanticCache(threshold=0.5)
    best.put("k", [1.0, 0.0], "first")
    best.put("k", [0.7, 0.7], "second")
    assert best.get("k", [0.6, 0.8]) == "second"
    small = SemanticCache(threshold=0.99, capacity=2)
    small.put("k", [1.0, 0.0], "a")
    small.put("k", [0.0, 1.0], "b")
    small.put("k", [0.6, 0.8], "c")
    assert small.get("k", [1.0, 0.0]) is None
    assert small.get("k", [0.0, 1.0]) == "b" and small.get("k", [0.6, 0.8]) == "c"


class FakeRetriever(Retriever):
    def __init__(self) -> None:
        self.embedder = HashEmbedder(64)
        self.strategy = None  # type: ignore[assignment]
        self.calls = 0

    def search(self, query: str, **kwargs: Any) -> list[Any]:
        self.calls += 1
        return [f"hit for {query}"]


def test_a_near_duplicate_question_is_answered_from_the_cache() -> None:
    inner = FakeRetriever()
    cached = CachedRetriever(inner, SemanticCache(threshold=0.9))
    filt = SearchFilter()
    first = cached.search("how long is the return window", filt=filt, k=5)
    again = cached.search("how long is the return window", filt=filt, k=5)
    other = cached.search("when does my subscription renew", filt=filt, k=5)
    assert first == again == ["hit for how long is the return window"]
    assert other == ["hit for when does my subscription renew"] and inner.calls == 2


def test_search_options_are_part_of_the_cache_key() -> None:
    inner = FakeRetriever()
    cached = CachedRetriever(inner, SemanticCache(threshold=0.9))
    cached.search("return window", filt=SearchFilter(), k=5)
    cached.search("return window", filt=SearchFilter(), k=3)
    assert inner.calls == 2


def test_a_cache_hit_is_visible_in_the_trace() -> None:
    exporter = InMemorySpanExporter()
    telemetry.configure([exporter])
    cached = CachedRetriever(FakeRetriever(), SemanticCache(threshold=0.9))
    cached.search("return window", filt=SearchFilter())
    cached.search("return window", filt=SearchFilter())
    telemetry.shutdown()
    hits = [span_record(s)["attributes"]["cache_hit"] for s in exporter.get_finished_spans()]
    assert hits == [False, True]
