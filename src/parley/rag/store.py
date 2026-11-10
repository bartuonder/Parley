from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from parley.rag.chunking import ChunkStrategy
from parley.rag.models import Chunk
from parley.rag.tables import ChunkEmbeddingRow, ChunkRow


def index_chunks(
    session: Session, strategy: ChunkStrategy, chunks: list[Chunk], corpus_hash: str
) -> None:
    """Replace every stored chunk (and its embeddings) of one strategy."""
    session.execute(delete(ChunkRow).where(ChunkRow.strategy == strategy.value))
    session.add_all(
        ChunkRow(
            strategy=strategy.value,
            corpus_hash=corpus_hash,
            **c.model_dump(mode="python", exclude={"regions"}),
            regions=[r.value for r in c.regions],
        )
        for c in chunks
    )
    session.flush()


def load_chunks(session: Session, strategy: ChunkStrategy) -> list[Chunk]:
    stmt = select(ChunkRow).where(ChunkRow.strategy == strategy.value).order_by(ChunkRow.id)
    return [_to_chunk(row) for row in session.scalars(stmt)]


def stored_corpus_hashes(session: Session, strategy: ChunkStrategy) -> set[str]:
    stmt = select(ChunkRow.corpus_hash).where(ChunkRow.strategy == strategy.value).distinct()
    return set(session.scalars(stmt))


def save_embeddings(
    session: Session, strategy: ChunkStrategy, model: str, vectors: dict[str, list[float]]
) -> None:
    """Store one vector per chunk id for a model, replacing earlier vectors of that model."""
    pks = _chunk_pks(session, strategy)
    missing = sorted(set(vectors) - set(pks))
    if missing:
        raise KeyError(f"unknown chunk ids: {missing[:3]}")
    session.execute(
        delete(ChunkEmbeddingRow).where(
            ChunkEmbeddingRow.model == model, ChunkEmbeddingRow.chunk_pk.in_(pks.values())
        )
    )
    session.add_all(
        ChunkEmbeddingRow(chunk_pk=pks[cid], model=model, embedding=vec)
        for cid, vec in vectors.items()
    )
    session.flush()


def load_embeddings(
    session: Session, strategy: ChunkStrategy, model: str
) -> dict[str, list[float]]:
    stmt = (
        select(ChunkRow.chunk_id, ChunkEmbeddingRow.embedding)
        .join(ChunkEmbeddingRow, ChunkEmbeddingRow.chunk_pk == ChunkRow.id)
        .where(ChunkRow.strategy == strategy.value, ChunkEmbeddingRow.model == model)
        .order_by(ChunkRow.id)
    )
    return {cid: [float(x) for x in vec] for cid, vec in session.execute(stmt)}


def _chunk_pks(session: Session, strategy: ChunkStrategy) -> dict[str, int]:
    stmt = select(ChunkRow.chunk_id, ChunkRow.id).where(ChunkRow.strategy == strategy.value)
    return {cid: pk for cid, pk in session.execute(stmt)}


def _to_chunk(row: ChunkRow) -> Chunk:
    return Chunk(
        chunk_id=row.chunk_id,
        doc_id=row.doc_id,
        version=row.version,
        title=row.title,
        category=row.category,
        regions=row.regions,
        effective_date=row.effective_date,
        expires_date=row.expires_date,
        section=row.section,
        text=row.text,
    )
