from dataclasses import dataclass
from datetime import date

from parley.policies.models import Region
from parley.rag.models import Chunk


@dataclass(frozen=True)
class SearchFilter:
    """Metadata filter; with as_of unset nothing is filtered, which exposes stale versions."""

    as_of: date | None = None
    region: Region | None = None
    latest_only: bool = True


def apply_filters(chunks: list[Chunk], filt: SearchFilter) -> list[Chunk]:
    kept = chunks
    if filt.region is not None:
        kept = [c for c in kept if c.applies_to(filt.region)]
    if filt.as_of is None:
        return kept
    kept = [c for c in kept if c.is_in_force(filt.as_of)]
    if not filt.latest_only:
        return kept
    newest: dict[str, int] = {}
    for c in kept:
        newest[c.doc_id] = max(newest.get(c.doc_id, 0), c.version)
    return [c for c in kept if c.version == newest[c.doc_id]]
