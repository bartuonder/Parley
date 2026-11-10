import math

import pytest
from sqlalchemy.orm import Session

from parley.policies.loader import load_policies
from parley.rag.chunking import ChunkStrategy
from parley.rag.embedders import HashEmbedder, get_embedder
from parley.rag.indexing import build_index
from parley.rag.rerankers import OverlapReranker, get_reranker
from parley.rag.store import load_chunks, load_embeddings


def cosine(a: list[float], b: list[float]) -> float:
    return sum(x * y for x, y in zip(a, b, strict=True))


def test_hash_embedder_is_deterministic_and_normalized() -> None:
    embedder = HashEmbedder(64)
    first = embedder.embed_query("Refund within thirty days")
    assert first == embedder.embed_query("Refund within thirty days")
    assert math.isclose(math.sqrt(sum(x * x for x in first)), 1.0)
    assert len(first) == 64


def test_hash_embedder_puts_overlapping_texts_closer() -> None:
    embedder = HashEmbedder()
    query = embedder.embed_query("refund window for returns")
    related = embedder.embed_query("returns are refunded inside the window")
    unrelated = embedder.embed_query("tracking numbers for parcels")
    assert cosine(query, related) > cosine(query, unrelated)


def test_hash_embedder_handles_empty_text() -> None:
    assert not any(HashEmbedder(8).embed_query(""))


def test_get_embedder_resolves_hash_names_and_rejects_unknown() -> None:
    assert get_embedder("hash-32").name == "hash-32"
    with pytest.raises(KeyError, match="unknown embedding model"):
        get_embedder("not-a-model")


def test_build_index_stores_chunks_and_vectors_per_embedder(session: Session) -> None:
    docs = load_policies()[:6]
    embedders = [HashEmbedder(32), HashEmbedder(64)]
    count = build_index(session, docs, ChunkStrategy.SECTION, embedders)

    chunks = load_chunks(session, ChunkStrategy.SECTION)
    assert len(chunks) == count
    small = load_embeddings(session, ChunkStrategy.SECTION, "hash-32")
    large = load_embeddings(session, ChunkStrategy.SECTION, "hash-64")
    assert list(small) == [c.chunk_id for c in chunks]
    assert len(next(iter(small.values()))) == 32
    assert len(next(iter(large.values()))) == 64


@pytest.mark.model
def test_real_model_ranks_a_relevant_passage_above_an_unrelated_one() -> None:
    embedder = get_embedder("bge-small")
    docs = embedder.embed_documents(
        [
            "Physical items can be returned within 30 days of delivery.",
            "Customs duties are the customer's responsibility for international parcels.",
        ]
    )
    query = embedder.embed_query("how long do I have to send an item back?")
    assert len(query) == 384
    assert cosine(query, docs[0]) > cosine(query, docs[1])


def test_embedders_are_loaded_once_per_name() -> None:
    assert get_embedder("hash-48") is get_embedder("hash-48")
    assert get_embedder("hash-48") is not get_embedder("hash-49")


def test_reranker_is_loaded_once(monkeypatch: pytest.MonkeyPatch) -> None:
    loads: list[int] = []

    class FakeCrossEncoder(OverlapReranker):
        def __init__(self) -> None:
            loads.append(1)

    get_reranker.cache_clear()
    monkeypatch.setattr("parley.rag.rerankers.CrossEncoderReranker", FakeCrossEncoder)
    assert get_reranker() is get_reranker()
    assert len(loads) == 1
    get_reranker.cache_clear()
