import math
from collections import OrderedDict
from collections.abc import Hashable
from typing import Any

from parley.observability.tracing import span
from parley.rag.retrieval import Hit, Retriever


def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm = math.sqrt(sum(x * x for x in a)) * math.sqrt(sum(y * y for y in b))
    return dot / norm if norm else 0.0


class SemanticCache:
    """Reuses an earlier answer for a query close enough in meaning, within the same key."""

    def __init__(self, threshold: float = 0.92, capacity: int = 256) -> None:
        self.threshold = threshold
        self.capacity = capacity
        self.hits = 0
        self.misses = 0
        self._entries: OrderedDict[int, tuple[Hashable, list[float], Any]] = OrderedDict()
        self._next = 0

    def get(self, key: Hashable, vector: list[float]) -> Any | None:
        best_id, best = None, self.threshold
        for entry_id, (entry_key, entry_vector, _) in self._entries.items():
            if entry_key != key:
                continue
            similarity = cosine(vector, entry_vector)
            if similarity >= best:
                best_id, best = entry_id, similarity
        if best_id is None:
            self.misses += 1
            return None
        self.hits += 1
        self._entries.move_to_end(best_id)
        return self._entries[best_id][2]

    def put(self, key: Hashable, vector: list[float], value: Any) -> None:
        self._entries[self._next] = (key, vector, value)
        self._next += 1
        while len(self._entries) > self.capacity:
            self._entries.popitem(last=False)

    @property
    def hit_rate(self) -> float:
        total = self.hits + self.misses
        return self.hits / total if total else 0.0


class CachedRetriever(Retriever):
    """A retriever that answers a near-duplicate question from the cache instead of searching."""

    def __init__(self, inner: Retriever, cache: SemanticCache) -> None:
        self.__dict__.update(inner.__dict__)
        self._inner = inner
        self._cache = cache

    def search(self, query: str, **kwargs: Any) -> list[Hit]:
        filt = kwargs.get("filt")
        key = (
            str(getattr(filt, "as_of", None)),
            str(getattr(filt, "region", None)),
            tuple(sorted((k, str(v)) for k, v in kwargs.items() if k != "filt")),
        )
        vector = self.embedder.embed_query(query)
        with span("rag.search", "rag") as handle:
            cached = self._cache.get(key, vector)
            handle.set(cache_hit=cached is not None)
            if cached is not None:
                return list(cached)
            hits = self._inner.search(query, **kwargs)
            self._cache.put(key, vector, hits)
            return hits
