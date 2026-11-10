from parley.rag.retrieval import Hit


def format_context(hits: list[Hit]) -> str:
    """Numbered, citable passages for an agent prompt."""
    blocks = []
    for hit in hits:
        c = hit.chunk
        header = f"[{hit.rank}] {c.citation} (effective {c.effective_date})"
        blocks.append(f"{header}\n{c.text}")
    return "\n\n".join(blocks)


def source_list(hits: list[Hit]) -> list[str]:
    """Unique policy versions behind a set of hits, in rank order."""
    return list(dict.fromkeys(h.chunk.doc_key for h in hits))
