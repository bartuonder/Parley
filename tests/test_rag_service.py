from datetime import date

from sqlalchemy.orm import Session

from parley.policies.loader import load_policies
from parley.policies.models import Region
from parley.rag.chunking import ChunkStrategy
from parley.rag.embedders import HashEmbedder
from parley.rag.rerankers import OverlapReranker
from parley.rag.service import (
    DEFAULT_STRATEGY,
    build_default_index,
    default_retriever,
    search_policies,
)
from parley.rag.store import load_chunks

EMBEDDER = HashEmbedder(256)
JUNE = date(2026, 6, 1)


def test_default_strategy_is_section_level_chunking() -> None:
    assert DEFAULT_STRATEGY == ChunkStrategy.SECTION


def test_build_default_index_stores_section_chunks(session: Session) -> None:
    count = build_default_index(session, embedder=EMBEDDER)
    assert count == len(load_chunks(session, DEFAULT_STRATEGY))
    assert count > len(load_policies())


def test_search_policies_returns_cited_in_force_hits(session: Session) -> None:
    build_default_index(session, embedder=EMBEDDER)
    retriever = default_retriever(session, EMBEDDER, OverlapReranker())
    hits = search_policies(retriever, "how many days to return an item", JUNE)
    assert 0 < len(hits) <= 5
    assert all(h.chunk.is_in_force(JUNE) for h in hits)
    assert "POL-REF-001@v1" not in {h.chunk.doc_key for h in hits}
    assert "POL-REF-001@v3" not in {h.chunk.doc_key for h in hits}
    assert all(" / " in h.citation or h.chunk.section is None for h in hits)


def test_search_policies_respects_the_question_date(session: Session) -> None:
    build_default_index(session, embedder=EMBEDDER)
    retriever = default_retriever(session, EMBEDDER, OverlapReranker())
    after_change = search_policies(retriever, "how many days to return an item", date(2026, 7, 15))
    assert "POL-REF-001@v3" in {h.chunk.doc_key for h in after_change}


def test_search_policies_filters_regional_policies(session: Session) -> None:
    build_default_index(session, embedder=EMBEDDER)
    retriever = default_retriever(session, EMBEDDER, OverlapReranker())
    us = search_policies(retriever, "statutory withdrawal right EU", JUNE, Region.US)
    assert "POL-REF-008@v1" not in {h.chunk.doc_key for h in us}
