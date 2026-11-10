from datetime import date

import pytest

from parley.policies.loader import load_policies
from parley.policies.models import PolicyCategory, PolicyDoc, Region
from parley.rag.chunking import (
    OVERLAP_WORDS,
    WINDOW_WORDS,
    ChunkStrategy,
    chunk_corpus,
    chunk_policy,
    split_sections,
)


def make_doc(body: str, **overrides: object) -> PolicyDoc:
    fields: dict[str, object] = {
        "doc_id": "POL-REF-001",
        "title": "Returns for physical goods",
        "version": 2,
        "effective_date": date(2025, 9, 1),
        "expires_date": date(2026, 12, 31),
        "category": PolicyCategory.REFUNDS,
        "regions": [Region.EU],
        "body": body,
    }
    fields.update(overrides)
    return PolicyDoc(**fields)


BODY = "## Window\n\nThirty days from delivery.\n\n## Condition\n\nUnused and boxed."


def test_split_sections_returns_heading_and_text() -> None:
    assert split_sections(BODY) == [
        ("Window", "Thirty days from delivery."),
        ("Condition", "Unused and boxed."),
    ]


def test_split_sections_keeps_text_before_first_heading() -> None:
    assert split_sections("Intro text.\n\n## Rule\n\nBody.") == [
        (None, "Intro text."),
        ("Rule", "Body."),
    ]


def test_section_strategy_makes_one_chunk_per_heading() -> None:
    chunks = chunk_policy(make_doc(BODY), ChunkStrategy.SECTION)
    assert [c.section for c in chunks] == ["Window", "Condition"]
    assert [c.chunk_id for c in chunks] == ["POL-REF-001@v2#0", "POL-REF-001@v2#1"]


def test_section_chunks_carry_title_version_and_date_in_text() -> None:
    text = chunk_policy(make_doc(BODY), ChunkStrategy.SECTION)[0].text
    assert "Returns for physical goods" in text
    assert "version 2" in text
    assert "2025-09-01" in text
    assert "Thirty days from delivery." in text


def test_chunks_copy_policy_metadata() -> None:
    chunk = chunk_policy(make_doc(BODY), ChunkStrategy.SECTION)[0]
    assert chunk.doc_key == "POL-REF-001@v2"
    assert chunk.citation == "POL-REF-001@v2 / Window"
    assert chunk.regions == [Region.EU]
    assert chunk.expires_date == date(2026, 12, 31)
    assert chunk.category == PolicyCategory.REFUNDS


def test_document_strategy_is_one_chunk_without_section() -> None:
    chunks = chunk_policy(make_doc(BODY), ChunkStrategy.DOCUMENT)
    assert len(chunks) == 1
    assert chunks[0].section is None
    assert chunks[0].citation == "POL-REF-001@v2"
    assert "Unused and boxed." in chunks[0].text


def test_fixed_strategy_short_doc_is_one_chunk_without_header() -> None:
    chunks = chunk_policy(make_doc(BODY), ChunkStrategy.FIXED)
    assert len(chunks) == 1
    assert "Returns for physical goods" not in chunks[0].text


@pytest.mark.parametrize("n_words", [80, 81, 100, 140, 250])
def test_fixed_windows_are_bounded_overlapping_and_cover_everything(n_words: int) -> None:
    words = [f"w{i}" for i in range(n_words)]
    chunks = chunk_policy(make_doc(" ".join(words)), ChunkStrategy.FIXED)
    pieces = [c.text.split() for c in chunks]
    assert all(len(p) <= WINDOW_WORDS for p in pieces)
    assert {w for p in pieces for w in p} == set(words)
    if len(pieces) > 1:
        assert set(pieces[0][-OVERLAP_WORDS:]) <= set(pieces[1])


def test_chunk_ids_are_unique_across_the_real_corpus() -> None:
    docs = load_policies()
    for strategy in ChunkStrategy:
        ids = [c.chunk_id for c in chunk_corpus(docs, strategy)]
        assert len(ids) == len(set(ids))


def test_real_corpus_chunk_counts_follow_strategy() -> None:
    docs = load_policies()
    by_doc = chunk_corpus(docs, ChunkStrategy.DOCUMENT)
    by_section = chunk_corpus(docs, ChunkStrategy.SECTION)
    assert len(by_doc) == len(docs)
    assert len(by_section) > len(by_doc)
    assert all(c.section for c in by_section)
