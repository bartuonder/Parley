import hashlib
import math
import re
from functools import cache
from pathlib import Path
from typing import Protocol

from parley.settings import get_settings

MODEL_REGISTRY: dict[str, str] = {
    "bge-small": "BAAI/bge-small-en-v1.5",
    "bge-base": "BAAI/bge-base-en-v1.5",
    "minilm": "sentence-transformers/all-MiniLM-L6-v2",
}
RERANKER_MODEL = "Xenova/ms-marco-MiniLM-L-6-v2"
WORD = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    name: str

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class HashEmbedder:
    """Deterministic bag-of-words hashing embedder; offline stand-in for tests and CI."""

    def __init__(self, dim: int = 256) -> None:
        self.dim = dim
        self.name = f"hash-{dim}"

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self.embed_query(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        vec = [0.0] * self.dim
        for word in WORD.findall(text.lower()):
            digest = hashlib.blake2b(word.encode(), digest_size=8).digest()
            value = int.from_bytes(digest, "big")
            vec[value % self.dim] += 1.0 if (value >> 63) & 1 else -1.0
        norm = math.sqrt(sum(x * x for x in vec))
        return [x / norm for x in vec] if norm else vec


class FastEmbedder:
    """Local ONNX embedding model with the query and passage handling of its family."""

    def __init__(self, alias: str, cache_dir: Path | None = None) -> None:
        from fastembed import TextEmbedding

        self.name = alias
        directory = cache_dir or get_settings().model_cache_dir
        self._model = TextEmbedding(MODEL_REGISTRY[alias], cache_dir=str(directory))

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self._model.passage_embed(texts)]

    def embed_query(self, text: str) -> list[float]:
        return next(iter(self._model.query_embed(text))).tolist()


@cache
def get_embedder(name: str) -> Embedder:
    """Load an embedder once per process; loading a real model takes seconds."""
    if name.startswith("hash-"):
        return HashEmbedder(int(name.removeprefix("hash-")))
    if name not in MODEL_REGISTRY:
        raise KeyError(f"unknown embedding model {name!r}; choose from {sorted(MODEL_REGISTRY)}")
    return FastEmbedder(name)
