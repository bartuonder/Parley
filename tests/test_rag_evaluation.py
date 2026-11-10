from datetime import date

import pytest
from sqlalchemy.orm import Session

from parley.policies.loader import load_policies
from parley.policies.models import PolicyCategory, Region
from parley.rag.chunking import ChunkStrategy, chunk_corpus
from parley.rag.embedders import HashEmbedder
from parley.rag.evaluation import (
    Gold,
    Question,
    aggregate,
    evaluate,
    is_relevant,
    load_questions,
    normalize,
    score_question,
)
from parley.rag.filters import SearchFilter, apply_filters
from parley.rag.indexing import build_index
from parley.rag.models import Chunk
from parley.rag.retrieval import Hit, Mode, Retriever

QUESTIONS = load_questions()
DOCS = load_policies()


def make_chunk(
    doc_id: str = "POL-REF-001", version: int = 2, text: str = "within 30 days"
) -> Chunk:
    return Chunk(
        chunk_id=f"{doc_id}@v{version}#0",
        doc_id=doc_id,
        version=version,
        title="t",
        category=PolicyCategory.REFUNDS,
        regions=[Region.GLOBAL],
        effective_date=date(2025, 9, 1),
        expires_date=None,
        section="s",
        text=text,
    )


def hits_of(*chunks: Chunk) -> list[Hit]:
    return [Hit(chunk=c, score=1.0, rank=i) for i, c in enumerate(chunks, start=1)]


def question(*gold: Gold) -> Question:
    return Question(id="Q001", question="q", gold=list(gold))


GOLD = Gold(doc="POL-REF-001@v2", evidence="within 30 days")


def test_question_set_is_large_and_has_unique_ids() -> None:
    ids = [q.id for q in QUESTIONS]
    assert len(QUESTIONS) >= 100
    assert len(ids) == len(set(ids))


def test_split_is_roughly_seventy_thirty() -> None:
    test_share = sum(q.split == "test" for q in QUESTIONS) / len(QUESTIONS)
    assert 0.25 <= test_share <= 0.35


def test_every_gold_evidence_phrase_exists_in_its_policy() -> None:
    bodies = {d.key: normalize(d.body) for d in DOCS}
    for q in QUESTIONS:
        for g in q.gold:
            assert g.doc in bodies, (q.id, g.doc)
            assert normalize(g.evidence) in bodies[g.doc], (q.id, g.evidence)


def test_every_gold_policy_version_is_in_force_on_the_question_date() -> None:
    chunks = chunk_corpus(DOCS, ChunkStrategy.DOCUMENT)
    for q in QUESTIONS:
        in_force = {c.doc_key for c in apply_filters(chunks, SearchFilter(as_of=q.as_of))}
        for g in q.gold:
            assert g.doc in in_force, (q.id, g.doc, q.as_of)


def test_questions_cover_stale_traps_and_regions() -> None:
    assert sum(q.as_of != date(2026, 6, 1) for q in QUESTIONS) >= 15
    assert any(q.region is not None for q in QUESTIONS)


def test_relevance_needs_the_right_version_and_the_evidence() -> None:
    assert is_relevant(make_chunk(), GOLD)
    assert not is_relevant(make_chunk(version=1), GOLD)
    assert not is_relevant(make_chunk(text="within 14 days"), GOLD)
    assert is_relevant(make_chunk(text="Return   WITHIN 30\ndays now"), GOLD)


def test_score_rewards_an_early_relevant_hit() -> None:
    other = make_chunk("POL-SHP-001", text="unrelated")
    first = score_question(question(GOLD), hits_of(make_chunk(), other), {"POL-REF-001@v2"})
    third = score_question(question(GOLD), hits_of(other, other, make_chunk()), {"POL-REF-001@v2"})
    assert first.recall_at == {1: 1.0, 3: 1.0, 5: 1.0}
    assert first.reciprocal_rank == 1.0
    assert third.recall_at == {1: 0.0, 3: 1.0, 5: 1.0}
    assert third.reciprocal_rank == pytest.approx(1 / 3)


def test_recall_is_the_share_of_gold_items_found() -> None:
    second = Gold(doc="POL-REF-002@v1", evidence="45 days")
    result = score_question(question(GOLD, second), hits_of(make_chunk()), set())
    assert result.recall_at[5] == 0.5


def test_miss_scores_zero_and_stale_hits_are_counted() -> None:
    old = make_chunk(version=1, text="within 14 days")
    result = score_question(question(GOLD), hits_of(old, old), {"POL-REF-001@v2"})
    assert result.recall_at[5] == 0.0
    assert result.reciprocal_rank == 0.0
    assert result.stale_rate == 1.0


def test_no_hits_scores_zero_without_dividing_by_zero() -> None:
    result = score_question(question(GOLD), [], set())
    assert result.recall_at[5] == 0.0
    assert result.stale_rate == 0.0


def test_aggregate_averages_over_questions() -> None:
    hit = score_question(question(GOLD), hits_of(make_chunk()), set())
    miss = score_question(question(GOLD), [], set())
    metrics = aggregate([hit, miss])
    assert metrics.n == 2
    assert metrics.recall_at_1 == 0.5
    assert metrics.mrr == 0.5
    assert aggregate([]).n == 0


def test_metadata_filter_removes_stale_hits_end_to_end(session: Session) -> None:
    embedder = HashEmbedder()
    build_index(session, DOCS, ChunkStrategy.SECTION, [embedder])
    retriever = Retriever(session, ChunkStrategy.SECTION, embedder)
    with_filter = evaluate(retriever, QUESTIONS, mode=Mode.HYBRID, rerank=False)
    without = evaluate(retriever, QUESTIONS, mode=Mode.HYBRID, rerank=False, use_filter=False)
    assert with_filter.n == len(QUESTIONS)
    assert with_filter.stale_rate == 0.0
    assert without.stale_rate > 0.0
    assert with_filter.recall_at_5 > without.recall_at_5
