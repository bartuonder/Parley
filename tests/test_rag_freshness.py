from datetime import date
from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.orm import Session

from parley.policies.loader import load_policies
from parley.policies.models import PolicyCategory, PolicyDoc, Region
from parley.rag.chunking import ChunkStrategy
from parley.rag.embedders import HashEmbedder
from parley.rag.freshness import StaleIndexError, assert_index_fresh, corpus_hash
from parley.rag.indexing import build_index
from parley.rag.rerankers import OverlapReranker
from parley.rag.service import build_default_index, default_retriever
from parley.rag.store import stored_corpus_hashes

SECTION = ChunkStrategy.SECTION
EMBEDDER = HashEmbedder(64)


def doc(**overrides: Any) -> PolicyDoc:
    fields: dict[str, Any] = {
        "doc_id": "POL-REF-001",
        "title": "Returns",
        "version": 1,
        "effective_date": date(2025, 1, 1),
        "category": PolicyCategory.REFUNDS,
        "body": "## Rule\n\ntext",
    }
    fields.update(overrides)
    return PolicyDoc(**fields)


def test_hash_is_stable_and_ignores_document_order() -> None:
    a, b = doc(), doc(doc_id="POL-SHP-001")
    assert corpus_hash([a, b]) == corpus_hash([b, a])
    assert corpus_hash([a, b]) == corpus_hash([a.model_copy(), b.model_copy()])


@pytest.mark.parametrize(
    "changed",
    [
        {"body": "## Rule\n\ndifferent text"},
        {"version": 2},
        {"effective_date": date(2025, 2, 1)},
        {"expires_date": date(2026, 1, 1)},
        {"regions": [Region.EU]},
        {"title": "Other title"},
    ],
)
def test_hash_changes_when_any_policy_field_changes(changed: dict[str, Any]) -> None:
    assert corpus_hash([doc()]) != corpus_hash([doc(**changed)])


def test_hash_changes_when_a_policy_is_added() -> None:
    assert corpus_hash([doc()]) != corpus_hash([doc(), doc(doc_id="POL-SHP-001")])


def test_build_index_records_the_corpus_hash(session: Session) -> None:
    docs = [doc(), doc(doc_id="POL-SHP-001")]
    build_index(session, docs, SECTION, [EMBEDDER])
    assert stored_corpus_hashes(session, SECTION) == {corpus_hash(docs)}


def test_fresh_index_passes_the_check(session: Session) -> None:
    docs = [doc()]
    build_index(session, docs, SECTION, [EMBEDDER])
    assert_index_fresh(session, SECTION, docs)


def test_missing_index_is_reported(session: Session) -> None:
    with pytest.raises(StaleIndexError, match="no section index"):
        assert_index_fresh(session, SECTION, [doc()])


def test_changed_corpus_makes_the_index_stale(session: Session) -> None:
    build_index(session, [doc()], SECTION, [EMBEDDER])
    with pytest.raises(StaleIndexError, match="different policy corpus"):
        assert_index_fresh(session, SECTION, [doc(body="## Rule\n\nedited")])


def test_rows_without_a_hash_count_as_stale(session: Session) -> None:
    build_index(session, [doc()], SECTION, [EMBEDDER])
    session.execute(text("UPDATE chunks SET corpus_hash = ''"))
    with pytest.raises(StaleIndexError):
        assert_index_fresh(session, SECTION, [doc()])


def test_default_retriever_refuses_a_stale_index(session: Session) -> None:
    build_default_index(session, embedder=EMBEDDER)
    default_retriever(session, EMBEDDER, OverlapReranker())
    changed = [*load_policies()[:-1]]
    with pytest.raises(StaleIndexError):
        default_retriever(session, EMBEDDER, OverlapReranker(), docs=changed)
