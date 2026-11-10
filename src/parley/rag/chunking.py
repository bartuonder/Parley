import re
from enum import StrEnum

from parley.policies.models import PolicyDoc
from parley.rag.models import Chunk

WINDOW_WORDS = 80
OVERLAP_WORDS = 20
SECTION_SPLIT = re.compile(r"(?m)^## ")


class ChunkStrategy(StrEnum):
    FIXED = "fixed"
    SECTION = "section"
    DOCUMENT = "document"


def chunk_corpus(docs: list[PolicyDoc], strategy: ChunkStrategy) -> list[Chunk]:
    chunks: list[Chunk] = []
    for doc in docs:
        chunks.extend(chunk_policy(doc, strategy))
    return chunks


def chunk_policy(doc: PolicyDoc, strategy: ChunkStrategy) -> list[Chunk]:
    if strategy == ChunkStrategy.FIXED:
        return _fixed(doc)
    if strategy == ChunkStrategy.SECTION:
        return _by_section(doc)
    return [_make(doc, 0, None, _header(doc) + "\n" + doc.body)]


def split_sections(body: str) -> list[tuple[str | None, str]]:
    """Split a policy body into (heading, text) pairs; text before the first heading has none."""
    parts = SECTION_SPLIT.split(body)
    sections: list[tuple[str | None, str]] = []
    if parts[0].strip():
        sections.append((None, parts[0].strip()))
    for part in parts[1:]:
        heading, _, text = part.partition("\n")
        sections.append((heading.strip(), text.strip()))
    return sections


def _header(doc: PolicyDoc) -> str:
    return (
        f"{doc.title} (policy {doc.doc_id}, version {doc.version}, effective {doc.effective_date})"
    )


def _by_section(doc: PolicyDoc) -> list[Chunk]:
    chunks = []
    for n, (heading, text) in enumerate(split_sections(doc.body)):
        label = f"## {heading}\n" if heading else ""
        chunks.append(_make(doc, n, heading, f"{_header(doc)}\n{label}{text}"))
    return chunks


def _fixed(doc: PolicyDoc) -> list[Chunk]:
    words = doc.body.split()
    step = WINDOW_WORDS - OVERLAP_WORDS
    chunks = []
    for n, start in enumerate(range(0, max(len(words) - OVERLAP_WORDS, 1), step)):
        window = words[start : start + WINDOW_WORDS]
        chunks.append(_make(doc, n, None, " ".join(window)))
    return chunks


def _make(doc: PolicyDoc, n: int, section: str | None, text: str) -> Chunk:
    return Chunk(
        chunk_id=f"{doc.key}#{n}",
        doc_id=doc.doc_id,
        version=doc.version,
        title=doc.title,
        category=doc.category,
        regions=doc.regions,
        effective_date=doc.effective_date,
        expires_date=doc.expires_date,
        section=section,
        text=text,
    )
