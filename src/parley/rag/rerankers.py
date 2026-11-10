from functools import cache
from pathlib import Path
from typing import Protocol

from parley.rag.bm25 import tokenize
from parley.rag.embedders import RERANKER_MODEL
from parley.settings import get_settings


class Reranker(Protocol):
    def score(self, query: str, texts: list[str]) -> list[float]: ...


class OverlapReranker:
    """Offline stand-in that scores by shared stemmed words; used in tests."""

    def score(self, query: str, texts: list[str]) -> list[float]:
        wanted = set(tokenize(query))
        return [len(wanted & set(tokenize(t))) / (len(wanted) or 1) for t in texts]


class CrossEncoderReranker:
    """Local ONNX cross-encoder that reads the query and a passage together."""

    def __init__(self, cache_dir: Path | None = None) -> None:
        from fastembed.rerank.cross_encoder import TextCrossEncoder

        directory = cache_dir or get_settings().model_cache_dir
        self._model = TextCrossEncoder(RERANKER_MODEL, cache_dir=str(directory))

    def score(self, query: str, texts: list[str]) -> list[float]:
        return [float(s) for s in self._model.rerank(query, texts)]


@cache
def get_reranker() -> Reranker:
    """Load the cross-encoder once per process."""
    return CrossEncoderReranker()
