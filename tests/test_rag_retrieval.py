from datetime import date

import pytest
from sqlalchemy.orm import Session

from parley.policies.models import PolicyCategory, PolicyDoc, Region
from parley.rag.chunking import ChunkStrategy
from parley.rag.embedders import HashEmbedder
from parley.rag.filters import SearchFilter
from parley.rag.indexing import build_index
from parley.rag.rerankers import OverlapReranker
from parley.rag.retrieval import Mode, Retriever, reciprocal_rank_fusion

EMBEDDER = HashEmbedder(256)
JUNE = date(2026, 6, 1)


def doc(doc_id: str, version: int, effective: date, body: str, **kw: object) -> PolicyDoc:
    return PolicyDoc(
        doc_id=doc_id,
        title="Policy",
        version=version,
        effective_date=effective,
        category=PolicyCategory.REFUNDS,
        body=body,
        **kw,
    )


DOCS = [
    doc("POL-REF-001", 1, date(2025, 1, 1), "## Return window\n\nReturn items within 14 days."),
    doc("POL-REF-001", 2, date(2025, 9, 1), "## Return window\n\nReturn items within 30 days."),
    doc(
        "POL-SHP-003", 1, date(2025, 1, 1), "## Late parcels\n\nA parcel past its estimate is late."
    ),
    doc("POL-SUB-002", 1, date(2025, 1, 1), "## Cancellation\n\nCancel a subscription any time."),
    doc(
        "POL-REF-008",
        1,
        date(2025, 1, 1),
        "## Withdrawal\n\nStatutory withdrawal right for consumers.",
        regions=[Region.EU],
    ),
]


@pytest.fixture
def retriever(session: Session) -> Retriever:
    build_index(session, DOCS, ChunkStrategy.SECTION, [EMBEDDER])
    return Retriever(session, ChunkStrategy.SECTION, EMBEDDER, OverlapReranker())


def top_docs(hits) -> list[str]:
    return [h.chunk.doc_key for h in hits]


@pytest.mark.parametrize("mode", list(Mode))
def test_each_mode_finds_the_matching_policy(retriever: Retriever, mode: Mode) -> None:
    hits = retriever.search("cancel my subscription", mode=mode, k=3)
    assert top_docs(hits)[0] == "POL-SUB-002@v1"


def test_hits_are_ranked_from_one_with_a_citation(retriever: Retriever) -> None:
    hits = retriever.search("late parcel", k=3)
    assert [h.rank for h in hits] == list(range(1, len(hits) + 1))
    assert hits[0].citation == "POL-SHP-003@v1 / Late parcels"


def test_k_limits_the_number_of_hits(retriever: Retriever) -> None:
    assert len(retriever.search("policy", mode=Mode.DENSE, k=2)) == 2


def test_without_a_filter_stale_versions_can_be_returned(retriever: Retriever) -> None:
    hits = retriever.search("return items within 14 days", mode=Mode.BM25, k=5)
    assert "POL-REF-001@v1" in top_docs(hits)


def test_as_of_filter_removes_the_superseded_version(retriever: Retriever) -> None:
    hits = retriever.search(
        "return items within 14 days", mode=Mode.BM25, filt=SearchFilter(as_of=JUNE), k=5
    )
    assert "POL-REF-001@v1" not in top_docs(hits)
    assert "POL-REF-001@v2" in top_docs(hits)


def test_region_filter_hides_regional_policies_from_other_regions(retriever: Retriever) -> None:
    query = "statutory withdrawal right"
    us = retriever.search(query, filt=SearchFilter(region=Region.US), k=5)
    eu = retriever.search(query, filt=SearchFilter(region=Region.EU), k=5)
    assert "POL-REF-008@v1" not in top_docs(us)
    assert top_docs(eu)[0] == "POL-REF-008@v1"


def test_filter_matching_nothing_returns_no_hits(retriever: Retriever) -> None:
    assert retriever.search("anything", filt=SearchFilter(as_of=date(2020, 1, 1))) == []


def test_reranker_reorders_first_stage_candidates(retriever: Retriever) -> None:
    query = "late parcel past estimate"
    plain = retriever.search(query, mode=Mode.DENSE, k=5, candidates=5)
    reranked = retriever.search(query, mode=Mode.DENSE, k=5, candidates=5, rerank=True)
    assert set(top_docs(plain)) == set(top_docs(reranked))
    assert top_docs(reranked)[0] == "POL-SHP-003@v1"


def test_rerank_requires_a_reranker(session: Session) -> None:
    build_index(session, DOCS, ChunkStrategy.SECTION, [EMBEDDER])
    bare = Retriever(session, ChunkStrategy.SECTION, EMBEDDER)
    with pytest.raises(ValueError, match="needs a reranker"):
        bare.search("x", rerank=True)


def test_dense_search_without_stored_embeddings_fails_clearly(session: Session) -> None:
    build_index(session, DOCS, ChunkStrategy.SECTION, [EMBEDDER])
    other = Retriever(session, ChunkStrategy.SECTION, HashEmbedder(64))
    with pytest.raises(LookupError, match="no embeddings"):
        other.search("cancel", mode=Mode.DENSE)


def test_rrf_rewards_agreement_between_rankers() -> None:
    fused = reciprocal_rank_fusion([["a", "b", "c"], ["b", "a", "d"]])
    assert fused["a"] == fused["b"]
    assert fused["a"] > fused["c"]
    assert fused["c"] == fused["d"]


def test_rrf_scores_an_item_missing_from_one_ranker_lower() -> None:
    fused = reciprocal_rank_fusion([["a", "b"], ["b", "c"]])
    assert fused["b"] > fused["a"]
    assert fused["b"] > fused["c"]
