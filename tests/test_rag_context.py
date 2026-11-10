from datetime import date

from parley.policies.models import PolicyCategory, Region
from parley.rag.context import format_context, source_list
from parley.rag.models import Chunk
from parley.rag.retrieval import Hit


def hit(rank: int, doc_id: str, version: int, section: str | None, text: str) -> Hit:
    chunk = Chunk(
        chunk_id=f"{doc_id}@v{version}#{rank}",
        doc_id=doc_id,
        version=version,
        title="t",
        category=PolicyCategory.REFUNDS,
        regions=[Region.GLOBAL],
        effective_date=date(2025, 9, 1),
        expires_date=None,
        section=section,
        text=text,
    )
    return Hit(chunk=chunk, score=1.0, rank=rank)


def test_context_numbers_passages_with_citation_and_effective_date() -> None:
    hits = [
        hit(1, "POL-REF-001", 2, "Return window", "Thirty days."),
        hit(2, "POL-SHP-003", 1, None, "Late parcels."),
    ]
    assert format_context(hits) == (
        "[1] POL-REF-001@v2 / Return window (effective 2025-09-01)\nThirty days.\n\n"
        "[2] POL-SHP-003@v1 (effective 2025-09-01)\nLate parcels."
    )


def test_empty_hits_give_empty_context() -> None:
    assert format_context([]) == ""
    assert source_list([]) == []


def test_source_list_deduplicates_in_rank_order() -> None:
    hits = [
        hit(1, "POL-REF-001", 2, "A", "x"),
        hit(2, "POL-SHP-003", 1, "B", "y"),
        hit(3, "POL-REF-001", 2, "C", "z"),
    ]
    assert source_list(hits) == ["POL-REF-001@v2", "POL-SHP-003@v1"]
