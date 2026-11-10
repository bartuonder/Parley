from collections.abc import Sequence

from sqlalchemy.orm import Session

from parley.policies.models import PolicyDoc
from parley.rag.chunking import ChunkStrategy, chunk_corpus
from parley.rag.embedders import Embedder
from parley.rag.store import index_chunks, save_embeddings


def build_index(
    session: Session,
    docs: list[PolicyDoc],
    strategy: ChunkStrategy,
    embedders: Sequence[Embedder],
) -> int:
    """Chunk the corpus, store the chunks, and store one vector set per embedder."""
    chunks = chunk_corpus(docs, strategy)
    index_chunks(session, strategy, chunks)
    ids = [c.chunk_id for c in chunks]
    texts = [c.text for c in chunks]
    for embedder in embedders:
        vectors = embedder.embed_documents(texts)
        save_embeddings(session, strategy, embedder.name, dict(zip(ids, vectors, strict=True)))
    return len(chunks)
